import logging
from typing import Optional
import stripe
from supabase import Client

logger = logging.getLogger(__name__)


async def _get_or_create_customer(supabase: Client, user_id: str, user_email: str) -> stripe.Customer:
    """Return an existing Stripe customer or create a new one."""
    user_response = supabase.table("users_metadata").select(
        "stripe_customer_id, name"
    ).eq("user_id", user_id).single().execute()

    customer_id: Optional[str] = None
    if user_response.data:
        customer_id = user_response.data.get("stripe_customer_id")

    if customer_id:
        try:
            return stripe.Customer.retrieve(customer_id)
        except stripe.error.StripeError:
            logger.warning("Stripe customer %s not found, creating new", customer_id)

    customer_name = user_response.data.get("name") if user_response.data else None
    customer = stripe.Customer.create(
        email=user_email,
        name=customer_name,
        metadata={"user_id": user_id},
    )

    supabase.table("users_metadata").update({
        "stripe_customer_id": customer.id
    }).eq("user_id", user_id).execute()

    logger.info("Created new Stripe customer %s for user %s", customer.id, user_id)
    return customer


async def ensure_stripe_customer(supabase: Client, user_id: str, user_email: str) -> stripe.Customer:
    """Public helper to ensure a Stripe customer exists for a user."""
    return await _get_or_create_customer(supabase, user_id, user_email)
