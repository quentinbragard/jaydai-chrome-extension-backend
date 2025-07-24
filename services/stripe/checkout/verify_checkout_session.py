import logging
from typing import Dict, Any
import stripe
from supabase import Client
from services.stripe.subscriptions import get_subscription_status, update_subscription_status
from utils.amplitude import track_event

logger = logging.getLogger(__name__)

async def verify_checkout_session(supabase: Client, session_id: str) -> Dict[str, Any]:
    """Verify a checkout session and return subscription details."""
    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
        user_id = session.metadata.get("user_id")
        if session.payment_status != "paid":
            if user_id:
                track_event(user_id, "payment_failed", {"session_id": session_id})
            return {"success": False, "error": "Payment not completed"}

        if not user_id:
            return {"success": False, "error": "User ID not found in session metadata"}

        if session.subscription:
            await update_subscription_status(supabase, user_id, session.subscription)

        sub_status = await get_subscription_status(supabase, user_id)
        track_event(user_id, "payment_succeeded", {"session_id": session_id})
        return {"success": True, "subscription": sub_status}
    except stripe.error.StripeError as e:
        logger.error("Stripe error verifying session: %s", e)
        if 'session' in locals():
            user_id = session.metadata.get("user_id") if session and session.metadata else None
            if user_id:
                track_event(user_id, "payment_failed", {"session_id": session_id, "error": str(e)})
        return {"success": False, "error": f"Payment verification failed: {e}"}
    except Exception as e:  # pragma: no cover - unexpected
        logger.error("Unexpected error verifying session: %s", e)
        if 'session' in locals():
            user_id = session.metadata.get("user_id") if session and session.metadata else None
            if user_id:
                track_event(user_id, "payment_failed", {"session_id": session_id, "error": str(e)})
        return {"success": False, "error": "An unexpected error occurred"}
