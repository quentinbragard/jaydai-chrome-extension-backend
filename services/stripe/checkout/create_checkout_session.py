import os
import logging
from typing import Dict, Any, Optional
import stripe
from supabase import Client

from services.stripe.customer import _get_or_create_customer
from services.stripe.helpers import _get_product_id_from_price
from services.stripe.subscriptions import get_subscription_status
from models.stripe import SubscriptionStatus

logger = logging.getLogger(__name__)


async def create_checkout_session(
    supabase: Client,
    price_id: str,
    user_id: str,
    auth_token: str,
    user_email: str,
    success_url: str,
    cancel_url: str,
    redirect_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a Stripe checkout session."""
    existing = await get_subscription_status(supabase, user_id)
    if existing.status == SubscriptionStatus.ACTIVE or existing.status == SubscriptionStatus.TRIALING:
        return {"success": False, "error": "User already has an active subscription"}

    customer = await _get_or_create_customer(supabase, user_id, user_email)
    product_id = _get_product_id_from_price(price_id)

    metadata = {
        "user_id": user_id,
        "auth_token": auth_token[:50] if auth_token else "",
        "created_via": "chrome_extension",
    }
    if product_id:
        metadata["product_id"] = product_id

    is_prod = os.getenv("ENVIRONMENT") == "prod"
    suffix = f"?session_id={{CHECKOUT_SESSION_ID}}"
    if auth_token:
        suffix += f"&auth_token={auth_token}"
    if redirect_url:
        suffix += f"&redirect_url={redirect_url}"
    if not is_prod:
        suffix += "&dev=true"

    session_params = {
        "customer": customer.id,
        "locale": "auto",
        "client_reference_id": user_id,
        "automatic_tax": {"enabled": True},
        "payment_method_types": ["card"],
        "line_items": [{"price": price_id, "quantity": 1}],
        "mode": "subscription",
        "success_url": success_url + suffix,
        "cancel_url": cancel_url,
        "metadata": metadata,
        "subscription_data": {
            "metadata": metadata,
            "trial_period_days": 3,
        },
        "allow_promotion_codes": True,
        "billing_address_collection": "auto",
        "customer_update": {"address": "auto", "name": "auto"},
    }

    try:
        session = stripe.checkout.Session.create(**session_params)
    except stripe.error.StripeError as e:
        logger.error("Stripe error creating checkout session: %s", e)
        return {"success": False, "error": f"Payment service error: {e}"}
    except Exception as e:  # pragma: no cover - unexpected
        logger.error("Unexpected error creating checkout session: %s", e)
        return {"success": False, "error": "An unexpected error occurred"}

    return {"success": True, "sessionId": session.id, "url": session.url}