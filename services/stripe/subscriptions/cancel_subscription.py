# services/stripe/subscriptions/cancel_subscription.py - FIXED IMPORT VERSION
import logging
import stripe
from supabase import Client
# FIX: Import the function directly from the module
from services.stripe.subscriptions.update_subscription_status import update_subscription_status

logger = logging.getLogger(__name__)

async def cancel_subscription(supabase: Client, user_id: str) -> bool:
    try:
        sub_resp = (
            supabase.table("stripe_subscriptions")
            .select("stripe_subscription_id")
            .eq("user_id", user_id)
            .in_("status", ["active", "trialing"])
            .execute()
        )

        subscription_id = None
        if sub_resp.data:
            subscription_id = sub_resp.data[0]["stripe_subscription_id"]
        else:
            logger.info(
                "Subscription not found in DB for user %s, checking Stripe", user_id
            )
            meta_resp = (
                supabase.table("users_metadata")
                .select("stripe_customer_id")
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            customer_id = meta_resp.data.get("stripe_customer_id") if meta_resp.data else None
            if customer_id:
                try:
                    subs = stripe.Subscription.list(
                        customer=customer_id, status="all", limit=1
                    )
                    if subs.data:
                        stripe_sub = subs.data[0]
                        if stripe_sub.status in ["active", "trialing"]:
                            subscription_id = stripe_sub.id
                except stripe.error.StripeError as e:
                    logger.error("Stripe error retrieving subscription: %s", e)
                    return False

        if not subscription_id:
            logger.warning(
                "No active or trialing subscription found for user %s", user_id
            )
            return False

        subscription = stripe.Subscription.modify(
            subscription_id, cancel_at_period_end=True
        )
        
        # This should now work correctly with the fixed import
        await update_subscription_status(supabase, user_id, subscription)
        logger.info("Cancelled subscription %s for user %s", subscription_id, user_id)
        return True
        
    except stripe.error.StripeError as e:
        logger.error("Stripe error cancelling subscription: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error cancelling subscription: %s", e)
        return False