import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from supabase import Client


logger = logging.getLogger(__name__)



async def record_webhook_event(supabase: Client, event_id: str, event_type: str, event_data: Dict[str, Any]) -> Optional[str]:
    try:
        resp = supabase.table("stripe_webhook_events").insert({
            "stripe_event_id": event_id,
            "event_type": event_type,
            "event_data": event_data,
        }).execute()
        if resp.data:
            return resp.data[0]["id"]
    except Exception as e:  # pragma: no cover - unexpected
        logger.error("Failed to record webhook event %s: %s", event_id, e)
    return None


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
