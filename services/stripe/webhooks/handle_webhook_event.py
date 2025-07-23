import logging
from typing import Dict, Any
from datetime import datetime, timezone
from supabase import Client

from .record_webhook_event import record_webhook_event
from .process_webhook_event import process_webhook_event

logger = logging.getLogger(__name__)


async def handle_webhook_event(supabase: Client, event: Dict[str, Any]) -> bool:
    event_id = event.get("id")
    event_type = event.get("type")
    event_data = event.get("data", {})

    existing = supabase.table("stripe_webhook_events").select("id, processed").eq("stripe_event_id", event_id).maybe_single().execute()
    if existing and existing.data and existing.data.get("processed"):
        logger.info("Event %s already processed", event_id)
        return True

    record_id = await record_webhook_event(supabase, event_id, event_type, event_data)

    try:
        success = await process_webhook_event(supabase, event_id, event_type, event_data)
        if record_id:
            supabase.table("stripe_webhook_events").update({"processed": success, "processed_at": datetime.now(timezone.utc).isoformat()}).eq("id", record_id).execute()
        return success
    except Exception as e:  # pragma: no cover - unexpected
        logger.error("Error processing webhook event %s: %s", event_type, e)
        if record_id:
            supabase.table("stripe_webhook_events").update({"processed": False, "processed_at": datetime.now(timezone.utc).isoformat()}).eq("id", record_id).execute()
        return False
