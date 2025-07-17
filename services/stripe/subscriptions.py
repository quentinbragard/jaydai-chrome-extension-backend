import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import stripe
from supabase import Client
from models.stripe import SubscriptionStatusResponse
from utils.stripe_config import stripe_config

logger = logging.getLogger(__name__)


async def get_subscription_status(supabase: Client, user_id: str) -> SubscriptionStatusResponse:
    try:
        sub_resp = supabase.table("stripe_subscriptions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
        user_meta = supabase.table("users_metadata").select("subscription_plan").eq("user_id", user_id).single().execute()
        if not sub_resp.data:
            return SubscriptionStatusResponse(
                isActive=False,
                planId=user_meta.data.get("subscription_plan") if user_meta.data else None,
                currentPeriodEnd=None,
                cancelAtPeriodEnd=False,
                stripeCustomerId=None,
                stripeSubscriptionId=None,
            )
        subscription = sub_resp.data[0]
        plan_id = user_meta.data.get("subscription_plan") if user_meta.data else None
        try:
            stripe_subscription = stripe.Subscription.retrieve(subscription["stripe_subscription_id"])
            if subscription["status"] != stripe_subscription.status:
                await _update_subscription_status(supabase, user_id, stripe_subscription)
                subscription["status"] = stripe_subscription.status
            is_active = stripe_subscription.status in ["active", "trialing"]
        except stripe.error.StripeError:
            logger.warning("Failed to retrieve subscription from Stripe for user %s", user_id)
            is_active = subscription["status"] in ["active", "trialing"]
        return SubscriptionStatusResponse(
            isActive=is_active,
            planId=plan_id,
            currentPeriodEnd=subscription["current_period_end"],
            cancelAtPeriodEnd=subscription["cancel_at_period_end"],
            stripeCustomerId=subscription["stripe_customer_id"],
            stripeSubscriptionId=subscription["stripe_subscription_id"],
        )
    except Exception as e:  # pragma: no cover - unexpected
        logger.error("Error getting subscription status for user %s: %s", user_id, e)
        return SubscriptionStatusResponse(isActive=False, planId=None, currentPeriodEnd=None, cancelAtPeriodEnd=False, stripeCustomerId=None, stripeSubscriptionId=None)


async def _update_subscription_status(supabase: Client, user_id: str, subscription: stripe.Subscription, stripe_event_id: Optional[str] = None):
    try:
        product_id = subscription.get('items').get('data')[0].get('plan').get('product')
        subscription_plan = "plus" if product_id == stripe_config.plus_product_id else None
        supabase.table("users_metadata").update({
            "subscription_status": subscription.status,
            "subscription_plan": subscription_plan,
            "stripe_customer_id": subscription.customer,
        }).eq("user_id", user_id).execute()
        data = {
            "user_id": user_id,
            "stripe_customer_id": subscription.customer,
            "stripe_subscription_id": subscription.id,
            "stripe_price_id": subscription.get('items').get('data')[0].get('price').get('id'),
            "stripe_product_id": product_id,
            "status": subscription.status,
            "current_period_start": datetime.fromtimestamp(subscription.current_period_start).isoformat(),
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end).isoformat(),
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "cancelled_at": datetime.fromtimestamp(subscription.canceled_at).isoformat() if subscription.canceled_at else None,
            "trial_start": datetime.fromtimestamp(subscription.trial_start).isoformat() if subscription.trial_start else None,
            "trial_end": datetime.fromtimestamp(subscription.trial_end).isoformat() if subscription.trial_end else None,
            "metadata": subscription.metadata or {},
        }
        existing = supabase.table("stripe_subscriptions").select("id").eq("stripe_subscription_id", subscription.id).execute()
        if existing.data:
            supabase.table("stripe_subscriptions").update(data).eq("stripe_subscription_id", subscription.id).execute()
        else:
            supabase.table("stripe_subscriptions").insert(data).execute()
        logger.info("Updated subscription status for user %s: %s", user_id, subscription.status)
    except Exception as e:  # pragma: no cover - unexpected
        logger.error("Failed to update subscription status for user %s: %s", user_id, e)


async def cancel_subscription(supabase: Client, user_id: str) -> bool:
    try:
        sub_resp = supabase.table("stripe_subscriptions").select("stripe_subscription_id").eq("user_id", user_id).eq("status", "active").or_("status.eq.trialing").execute()
        if not sub_resp.data:
            logger.warning("No active subscription found for user %s", user_id)
            return False
        subscription_id = sub_resp.data[0]["stripe_subscription_id"]
        subscription = stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        await _update_subscription_status(supabase, user_id, subscription)
        logger.info("Cancelled subscription %s for user %s", subscription_id, user_id)
        return True
    except stripe.error.StripeError as e:
        logger.error("Stripe error cancelling subscription: %s", e)
        return False
    except Exception as e:  # pragma: no cover - unexpected
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
    except Exception as e:  # pragma: no cover - unexpected
        logger.error("Unexpected error reactivating subscription: %s", e)
        return False


async def get_detailed_subscription_info(supabase: Client, user_id: str) -> Dict[str, Any]:
    try:
        sub_resp = supabase.table("stripe_subscriptions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
        user_meta = supabase.table("users_metadata").select("subscription_plan, name, email").eq("user_id", user_id).single().execute()
        if not sub_resp.data:
            return {"hasSubscription": False, "status": "inactive", "planId": user_meta.data.get("subscription_plan") if user_meta.data else None}
        subscription = sub_resp.data[0]
        user_metadata = user_meta.data or {}
        return {
            "hasSubscription": True,
            "status": subscription["status"],
            "planId": user_metadata.get("subscription_plan"),
            "currentPeriodStart": subscription["current_period_start"],
            "currentPeriodEnd": subscription["current_period_end"],
            "cancelAtPeriodEnd": subscription["cancel_at_period_end"],
            "cancelledAt": subscription.get("cancelled_at"),
            "trialStart": subscription.get("trial_start"),
            "trialEnd": subscription.get("trial_end"),
            "isTrialing": subscription["status"] == "trialing",
            "isActive": subscription["status"] in ["active", "trialing"],
            "isPastDue": subscription["status"] == "past_due",
            "isCancelled": subscription["status"] == "cancelled" or subscription["cancel_at_period_end"],
            "stripeCustomerId": subscription["stripe_customer_id"],
            "stripeSubscriptionId": subscription["stripe_subscription_id"],
        }
    except Exception as e:  # pragma: no cover - unexpected
        logger.error("Error getting detailed subscription info for user %s: %s", user_id, e)
        return {"hasSubscription": False, "status": "inactive", "planId": None}
