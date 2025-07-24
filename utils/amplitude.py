# utils/amplitude.py - Enhanced Amplitude service
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from amplitude import Amplitude, BaseEvent, Identify
except ImportError:  # pragma: no cover - amplitude optional
    Amplitude = None
    BaseEvent = None
    Identify = None

logger = logging.getLogger(__name__)

class AmplitudeService:
    def __init__(self):
        self._api_key = os.getenv("AMPLITUDE_API_KEY")
        self._client = Amplitude(self._api_key) if self._api_key and Amplitude else None
        self._environment = os.getenv("ENVIRONMENT", "dev")
        
        if not self._client:
            logger.warning("Amplitude not configured - events will not be tracked")
        else:
            logger.info(f"Amplitude initialized for environment: {self._environment}")

    def track_event(self, user_id: str, event_type: str, event_properties: Optional[Dict[str, Any]] = None):
        """Send an event to Amplitude if configured."""
        if not self._client or not BaseEvent:
            return

        try:
            # Add environment and timestamp to all events
            properties = event_properties or {}
            properties.update({
                "environment": self._environment,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "backend_api"
            })

            event = BaseEvent(
                event_type=event_type,
                user_id=user_id,
                event_properties=properties
            )
            
            self._client.track(event)
            logger.debug(f"Tracked event '{event_type}' for user {user_id}")
            
        except Exception as e:  # pragma: no cover - network issues
            logger.error(f"Failed to send amplitude event {event_type} for user {user_id}: {str(e)}")

    def identify_user(self, user_id: str, user_properties: Dict[str, Any]):
        """Update user properties in Amplitude."""
        if not self._client or not Identify:
            return

        try:
            identify = Identify()
            for key, value in user_properties.items():
                identify.set(key, value)
            
            self._client.identify(identify, user_id)
            logger.debug(f"Updated user properties for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to identify user {user_id}: {str(e)}")

    def track_revenue(self, user_id: str, amount: float, currency: str = "USD", 
                     product_id: Optional[str] = None, additional_properties: Optional[Dict[str, Any]] = None):
        """Track revenue events with special revenue properties."""
        if not self._client or not BaseEvent:
            return

        try:
            properties = additional_properties or {}
            properties.update({
                "revenue": amount,
                "currency": currency,
                "environment": self._environment,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "backend_api"
            })
            
            if product_id:
                properties["product_id"] = product_id

            event = BaseEvent(
                event_type="Revenue",
                user_id=user_id,
                event_properties=properties
            )
            
            self._client.track(event)
            logger.debug(f"Tracked revenue event for user {user_id}: ${amount} {currency}")
            
        except Exception as e:
            logger.error(f"Failed to track revenue for user {user_id}: {str(e)}")

# Global instance
amplitude_service = AmplitudeService()

# Backward compatibility functions
def track_event(user_id: str, event_type: str, event_properties: Optional[Dict[str, Any]] = None):
    """Backward compatible function for existing code."""
    amplitude_service.track_event(user_id, event_type, event_properties)

def identify_user(user_id: str, user_properties: Dict[str, Any]):
    """Update user properties."""
    amplitude_service.identify_user(user_id, user_properties)

def track_revenue(user_id: str, amount: float, currency: str = "USD", 
                 product_id: Optional[str] = None, additional_properties: Optional[Dict[str, Any]] = None):
    """Track revenue events."""
    amplitude_service.track_revenue(user_id, amount, currency, product_id, additional_properties)