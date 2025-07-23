import logging
from typing import Optional
import stripe
from supabase import Client

logger = logging.getLogger(__name__)


async def create_customer_portal_session(supabase: Client, user_id: str, return_url: str) -> Optional[str]:
    """Create a customer portal session for managing a subscription."""
    sub_resp = supabase.table("stripe_subscriptions").select("stripe_customer_id").eq("user_id", user_id).in_("status", ["active", "trialing"]).execute()

    if not sub_resp.data:
        logger.warning("No Stripe customer found for user %s", user_id)
        return None
    customer_id = sub_resp.data[0]["stripe_customer_id"]

    try:
        session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
        logger.info("Created customer portal session for user %s", user_id)
        return session.url
    except stripe.error.StripeError as e:
        logger.error("Stripe error creating customer portal: %s", e)
        return None
    except Exception as e:  # pragma: no cover - unexpected
        logger.error("Unexpected error creating customer portal: %s", e)
        return None
