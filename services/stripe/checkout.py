import os
import logging
from typing import Dict, Any, Optional
import stripe
from supabase import Client

from services.stripe.customer import _get_or_create_customer
from services.stripe.utils import _get_product_id_from_price, _get_plan_name_from_product_id
from . import subscriptions

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
    existing = await subscriptions.get_subscription_status(supabase, user_id)
    if existing.isActive:
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


async def verify_checkout_session(supabase: Client, session_id: str) -> Dict[str, Any]:
    """Verify a checkout session and return subscription details."""
    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
        if session.payment_status != "paid":
            return {"success": False, "error": "Payment not completed"}
        user_id = session.metadata.get("user_id")
        if not user_id:
            return {"success": False, "error": "User ID not found in session metadata"}
        if session.subscription:
            await subscriptions._update_subscription_status(supabase, user_id, session.subscription)
        sub_status = await subscriptions.get_subscription_status(supabase, user_id)
        return {"success": True, "subscription": sub_status}
    except stripe.error.StripeError as e:
        logger.error("Stripe error verifying session: %s", e)
        return {"success": False, "error": f"Payment verification failed: {e}"}
    except Exception as e:  # pragma: no cover - unexpected
        logger.error("Unexpected error verifying session: %s", e)
        return {"success": False, "error": "An unexpected error occurred"}
