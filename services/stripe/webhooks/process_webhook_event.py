import logging
from datetime import datetime, timezone
from typing import Dict, Any
from supabase import Client
import stripe
from services.stripe.subscriptions import update_subscription_status

logger = logging.getLogger(__name__)



async def process_webhook_event(supabase: Client, event_id: str, event_type: str, event_data: Dict[str, Any]) -> bool:
    handlers = {
        "customer.subscription.created": _handle_subscription_created,
        "customer.subscription.updated": _handle_subscription_updated,
        "customer.subscription.deleted": _handle_subscription_deleted,
        "invoice.payment_succeeded": _handle_payment_succeeded,
        "invoice.payment_failed": _handle_payment_failed,
    }
    handler = handlers.get(event_type)
    if handler:
        return await handler(supabase, event_id, event_data.get("object", {}))
    logger.info("No handler for event type: %s", event_type)
    return True

async def _handle_subscription_created(supabase: Client, event_id: str, subscription: Dict[str, Any]):
    user_id = subscription["metadata"].get("user_id")
    if user_id:
        stripe_subscription = stripe.Subscription.construct_from(subscription, stripe.api_key)
        await update_subscription_status(supabase, user_id, stripe_subscription)


async def _handle_subscription_updated(supabase: Client, event_id: str, subscription: Dict[str, Any]):
    user_id = subscription["metadata"].get("user_id")
    if user_id:
        stripe_subscription = stripe.Subscription.construct_from(subscription, stripe.api_key)
        await update_subscription_status(supabase, user_id, stripe_subscription)


async def _handle_subscription_deleted(supabase: Client, event_id: str, subscription: Dict[str, Any]):
    user_id = subscription["metadata"].get("user_id")
    if user_id:
        supabase.table("users_metadata").update({"subscription_status": "cancelled", "subscription_plan": None}).eq("user_id", user_id).execute()
        supabase.table("stripe_subscriptions").update({"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}).eq("user_id", user_id).execute()
        logger.info("Marked subscription as cancelled for user %s", user_id)


async def _handle_payment_succeeded(supabase: Client, event_id: str, invoice: Dict[str, Any]):
    subscription_id = invoice.get("subscription")
    if subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            user_id = subscription.metadata.get("user_id")
            if user_id:
                await update_subscription_status(supabase, user_id, subscription)
            return True
        except stripe.error.StripeError as e:
            logger.error("Failed to retrieve subscription %s: %s", subscription_id, e)
            return False
    return True


async def _handle_payment_failed(supabase: Client, event_id: str, invoice: Dict[str, Any]):
    subscription_id = invoice.get("subscription")
    if subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            user_id = subscription.metadata.get("user_id")
            if user_id:
                await update_subscription_status(supabase, user_id, subscription)
        except stripe.error.StripeError as e:
            logger.error("Failed to retrieve subscription %s: %s", subscription_id, e)
    return True
