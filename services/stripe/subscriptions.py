import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import stripe
from supabase import Client
from models.stripe import SubscriptionStatusResponse, SubscriptionStatus
from utils.stripe_config import stripe_config
from services.stripe.utils import _get_plan_name_from_product_id

logger = logging.getLogger(__name__)

async def get_subscription_status(supabase: Client, user_id: str) -> SubscriptionStatusResponse:
    try:
        sub_resp = supabase.table("stripe_subscriptions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
        user_meta = supabase.table("users_metadata").select("subscription_plan").eq("user_id", user_id).single().execute()
        print("==================================\n")
        print(user_meta.data)
        print("==================================\n")
        print(sub_resp.data)
        print("==================================\n")
        
        if not sub_resp.data:
            print("ICIIIIIIIIIIIIIIIIIII")
            return SubscriptionStatusResponse(
                status=SubscriptionStatus.INACTIVE,
                planName=user_meta.data.get("subscription_plan") if user_meta.data else None,
                createdAt=None,
                trialStart=None,
                trialEnd=None,
                currentPeriodStart=None,
                currentPeriodEnd=None,
                cancelAtPeriodEnd=False,
                stripeCustomerId=None,
                stripeSubscriptionId=None
            )
        subscription = sub_resp.data[0]

        plan_name = user_meta.data.get("subscription_plan") if user_meta.data else None
        try:
            stripe_subscription = stripe.Subscription.retrieve(subscription["stripe_subscription_id"])
            if subscription["status"] != stripe_subscription.status:
                await _update_subscription_status(supabase, user_id, stripe_subscription)
                subscription["status"] = stripe_subscription.status
        except stripe.error.StripeError as e:
            logger.warning("Failed to retrieve subscription from Stripe for user %s: %s", user_id, e)
        print("LAAAAAAAAAAAAA")
        print(subscription)
        print("LAAAAAAAAAAAAA")
        return SubscriptionStatusResponse(
            status=stripe_subscription.status,
            planName=plan_name,
            createdAt=subscription.get("created") if subscription.get("created") else None,
            trialStart=subscription.get("trial_start") if subscription.get("trial_start") else None,
            trialEnd=subscription.get("trial_end") if subscription.get("trial_end") else None,
            currentPeriodStart=subscription.get("current_period_start") if subscription.get("current_period_start") else None,
            currentPeriodEnd=subscription.get("current_period_end") if subscription.get("current_period_end") else None,
            cancelAtPeriodEnd=subscription.get("cancel_at_period_end") or False,
            stripeCustomerId=subscription.get("stripe_customer_id") or None,
            stripeSubscriptionId=subscription.get("stripe_subscription_id") or None,
        )
    except Exception as e:
        logger.error("Error getting subscription status for user %s: %s", user_id, e)
        return SubscriptionStatusResponse(status=SubscriptionStatus.INACTIVE, planName=None, currentPeriodEnd=None, cancelAtPeriodEnd=False, stripeCustomerId=None, stripeSubscriptionId=None)

async def _update_subscription_status(supabase: Client, user_id: str, subscription: stripe.Subscription, stripe_event_id: Optional[str] = None):
    try:
        product_id = subscription.get('items').get('data')[0].get('plan').get('product')
        plan_name = _get_plan_name_from_product_id(product_id)
        print("👇👇👇👇 plan_name 👇👇👇👇\n")
        print(plan_name)
        data = {
            "user_id": user_id,
            "stripe_customer_id": subscription.get("customer"),
            "stripe_subscription_id": subscription.get("id"),
            "stripe_price_id": subscription.get('items').get('data')[0].get('price').get('id'),
            "stripe_product_id": product_id,
            "status": subscription.get("status"),
            "current_period_start": datetime.fromtimestamp(subscription.get("current_period_start")).isoformat() if subscription.get("current_period_start") else None,
            "current_period_end": datetime.fromtimestamp(subscription.get("current_period_end")).isoformat() if subscription.get("current_period_end") else None,
            "cancel_at_period_end": subscription.get("cancel_at_period_end"),
            "cancelled_at": datetime.fromtimestamp(subscription.get("canceled_at")).isoformat() if subscription.get("canceled_at") else None,
            "trial_start": datetime.fromtimestamp(subscription.get("trial_start")).isoformat() if subscription.get("trial_start") else None,
            "trial_end": datetime.fromtimestamp(subscription.get("trial_end")).isoformat() if subscription.get("trial_end") else None,
            "metadata": subscription.get("metadata") or {},
        }
        existing = supabase.table("stripe_subscriptions").select("id").eq("stripe_subscription_id", subscription.get("id")).execute()
        if existing.data:
            supabase.table("stripe_subscriptions").update(data).eq("stripe_subscription_id", subscription.get("id")).execute()
        else:
            supabase.table("stripe_subscriptions").insert(data).execute()    
        supabase.table("users_metadata").update({"subscription_plan": plan_name}).eq("user_id", user_id).execute()
        logger.info("Updated subscription status for user %s: %s", user_id, subscription.get("status"))
    except Exception as e:
        logger.error("Failed to update subscription status for user %s: %s", user_id, e)

async def cancel_subscription(supabase: Client, user_id: str) -> bool:
    try:
        sub_resp = supabase.table("stripe_subscriptions").select("stripe_subscription_id").eq("user_id", user_id).in_("status", ["active", "trialing"]).execute()
        if not sub_resp.data:
            logger.warning("No active or trialing subscription found for user %s", user_id)
            return False
        subscription_id = sub_resp.data[0]["stripe_subscription_id"]
        subscription = stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        await _update_subscription_status(supabase, user_id, subscription)
        logger.info("Cancelled subscription %s for user %s", subscription_id, user_id)
        return True
    except stripe.error.StripeError as e:
        logger.error("Stripe error cancelling subscription: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error cancelling subscription: %s", e)
        return False

async def reactivate_subscription(supabase: Client, user_id: str) -> bool:
    try:
        sub_resp = supabase.table("stripe_subscriptions").select("stripe_subscription_id").eq("user_id", user_id).eq("cancel_at_period_end", True).execute()
        if not sub_resp.data:
            logger.warning("No cancelled subscription found for user %s", user_id)
            return False
        subscription_id = sub_resp.data[0]["stripe_subscription_id"]
        subscription = stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)
        await _update_subscription_status(supabase, user_id, subscription)
        logger.info("Reactivated subscription %s for user %s", subscription_id, user_id)
        return True
    except stripe.error.StripeError as e:
        logger.error("Stripe error reactivating subscription: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error reactivating subscription: %s", e)
        return False
