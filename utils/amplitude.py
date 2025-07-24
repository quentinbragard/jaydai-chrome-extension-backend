import os
import logging
try:
    from amplitude import Amplitude, BaseEvent
except Exception:  # pragma: no cover - amplitude optional
    Amplitude = None
    BaseEvent = None

_API_KEY = os.getenv("AMPLITUDE_API_KEY")
_client = Amplitude(_API_KEY) if _API_KEY and Amplitude else None
logger = logging.getLogger(__name__)


def track_event(user_id: str, event_type: str, event_properties: dict | None = None):
    """Send an event to Amplitude if configured."""
    if not _client:
        return
    try:
        event = BaseEvent(event_type=event_type, user_id=user_id, event_properties=event_properties or {})
        _client.track(event)
    except Exception as e:  # pragma: no cover - network issues
        logger.error("Failed to send amplitude event %s for user %s: %s", event_type, user_id, e)
