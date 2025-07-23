import logging
import stripe
from supabase import Client
from models.stripe import SubscriptionStatusResponse, SubscriptionStatus
from services.stripe.subscriptions import update_subscription_status

logger = logging.getLogger(__name__)

async def get_subscription_status(supabase: Client, user_id: str) -> SubscriptionStatusResponse:
    try:
        sub_resp = supabase.table("stripe_subscriptions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
        user_meta = supabase.table("users_metadata").select("subscription_plan").eq("user_id", user_id).single().execute()

        
        if not sub_resp.data:
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
                await update_subscription_status(supabase, user_id, stripe_subscription)
                subscription["status"] = stripe_subscription.status
        except stripe.error.StripeError as e:
            logger.warning("Failed to retrieve subscription from Stripe for user %s: %s", user_id, e)

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
