import logging
import stripe
from supabase import Client
from services.stripe.subscriptions.update_subscription_status import update_subscription_status

logger = logging.getLogger(__name__)

async def reactivate_subscription(supabase: Client, user_id: str) -> bool:
    try:
        sub_resp = supabase.table("stripe_subscriptions").select("stripe_subscription_id").eq("user_id", user_id).eq("cancel_at_period_end", True).execute()
        if not sub_resp.data:
            logger.warning("No cancelled subscription found for user %s", user_id)
            return False
        subscription_id = sub_resp.data[0]["stripe_subscription_id"]
        subscription = stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)
        await update_subscription_status(supabase, user_id, subscription)
        logger.info("Reactivated subscription %s for user %s", subscription_id, user_id)
        return True
    except stripe.error.StripeError as e:
        logger.error("Stripe error reactivating subscription: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error reactivating subscription: %s", e)
        return False
