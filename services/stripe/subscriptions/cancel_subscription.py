import logging
import stripe
from supabase import Client
from services.stripe.subscriptions import update_subscription_status

logger = logging.getLogger(__name__)

async def cancel_subscription(supabase: Client, user_id: str) -> bool:
    try:
        sub_resp = supabase.table("stripe_subscriptions").select("stripe_subscription_id").eq("user_id", user_id).in_("status", ["active", "trialing"]).execute()
        if not sub_resp.data:
            logger.warning("No active or trialing subscription found for user %s", user_id)
            return False
        subscription_id = sub_resp.data[0]["stripe_subscription_id"]
        subscription = stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        await update_subscription_status(supabase, user_id, subscription)
        logger.info("Cancelled subscription %s for user %s", subscription_id, user_id)
        return True
    except stripe.error.StripeError as e:
        logger.error("Stripe error cancelling subscription: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error cancelling subscription: %s", e)
        return False