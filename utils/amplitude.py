# utils/amplitude.py - Enhanced Amplitude service with proper session handling
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from amplitude import Amplitude, BaseEvent, Identify, Revenue, EventOptions
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
            
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[int]:
        """Parse ISO timestamp string to milliseconds since epoch (Amplitude format)."""
        if not timestamp_str:
            return None
            
        try:
            # Parse ISO format timestamp
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            # Convert to milliseconds since epoch (Amplitude expects this)
            return int(dt.timestamp() * 1000)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return None

    def _convert_session_id_to_int(self, session_id: Optional[str]) -> Optional[int]:
        """Convert session_id string to integer that Amplitude expects."""
        if not session_id:
            return None
            
        try:
            # If it's already a number string, convert directly
            if session_id.isdigit():
                return int(session_id)
            
            # For session strings like "session_1234567890_abc123", extract timestamp
            if session_id.startswith("session_"):
                parts = session_id.split("_")
                if len(parts) >= 2 and parts[1].isdigit():
                    return int(parts[1])
            
            # For other strings, create a hash-based integer
            # Use a simple hash that stays consistent for the same string
            return abs(hash(session_id)) % (2**31)  # Keep it within 32-bit int range
            
        except Exception as e:
            logger.warning(f"Failed to convert session_id '{session_id}' to int: {e}")
            # Fallback: use current timestamp
            return int(datetime.utcnow().timestamp())

    def track_event(self, user_id: str, event_type: str, event_properties: Optional[Dict[str, Any]] = None, 
                   session_id: Optional[str] = None, timestamp: Optional[str] = None, platform: Optional[str] = None,
                   location: Optional[Dict[str, Any]] = None):
        """Send an event to Amplitude if configured."""
        if not self._client or not BaseEvent:
            return

        try:
            # Extract session and timestamp from event_properties if provided there
            properties = event_properties or {}
            
            # Get session_id from parameter or event_properties and convert to int
            final_session_id_str = session_id or properties.pop("session_id", None)
            final_session_id = self._convert_session_id_to_int(final_session_id_str)
            
            # Get timestamp from parameter or event_properties
            final_timestamp = timestamp or properties.pop("timestamp", None)
            parsed_timestamp = self._parse_timestamp(final_timestamp)
            
            # Get platform from parameter or event_properties
            final_platform = platform or properties.pop("platform", None)
            
            # Get location from parameter or event_properties
            final_location = location or properties.pop("location", None)
            
            # Add environment to properties but remove session_id and timestamp 
            # since they go at the event level
            properties.update({
                "environment": self._environment,
                "source": "backend_api"
            })
            
            # Remove these from properties if they exist to avoid duplication
            properties.pop("timestamp", None)

            # Prepare location parameters for Amplitude's built-in location properties
            location_params = {}
            if final_location:
                if final_location.get("country"):
                    location_params["country"] = final_location["country"]
                if final_location.get("region"):
                    location_params["region"] = final_location["region"]
                if final_location.get("city"):
                    location_params["city"] = final_location["city"]
                if final_location.get("latitude") and final_location.get("longitude"):
                    location_params["location_lat"] = final_location["latitude"]
                    location_params["location_lng"] = final_location["longitude"]
                if final_location.get("ip"):
                    location_params["ip"] = final_location["ip"]

            # Create the event with proper session and location handling
            event = BaseEvent(
                event_type=event_type,
                user_id=user_id,
                event_properties=properties,
                time=parsed_timestamp,  # This sets the event timestamp
                session_id=final_session_id,  # This associates the event with a session (as int)
                platform=final_platform,  # This sets the platform
                **location_params  # This sets Amplitude's built-in location properties
            )
            
            self._client.track(event)
            logger.debug(f"Tracked event '{event_type}' for user {user_id} with session {final_session_id} on platform {final_platform} in {final_location.get('city', 'unknown') if final_location else 'unknown'}")
            
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
                     product_id: Optional[str] = None, additional_properties: Optional[Dict[str, Any]] = None,
                     session_id: Optional[str] = None, platform: Optional[str] = None, 
                     location: Optional[Dict[str, Any]] = None):
        """Track revenue events with special revenue properties."""
        if not self._client or not BaseEvent:
            return

        try:
            properties = additional_properties or {}
            properties.update({
                "revenue": amount,
                "currency": currency,
                "environment": self._environment,
                "source": "backend_api"
            })
            
            if product_id:
                properties["product_id"] = product_id

            # Convert session_id to int
            final_session_id = self._convert_session_id_to_int(session_id)

            # Prepare location parameters
            location_params = {}
            if location:
                if location.get("country"):
                    location_params["country"] = location["country"]
                if location.get("region"):
                    location_params["region"] = location["region"]
                if location.get("city"):
                    location_params["city"] = location["city"]
                if location.get("latitude") and location.get("longitude"):
                    location_params["location_lat"] = location["latitude"]
                    location_params["location_lng"] = location["longitude"]
                if location.get("ip"):
                    location_params["ip"] = location["ip"]

            event = BaseEvent(
                event_type="Revenue",
                user_id=user_id,
                event_properties=properties,
                session_id=final_session_id,  # Include session for revenue events too (as int)
                platform=platform,  # Include platform
                time=int(datetime.utcnow().timestamp() * 1000),
                **location_params  # Include location
            )
            
            self._client.track(event)
            revenue_obj = Revenue(price=amount,
                      quantity=1,
                      product_id=product_id)
            
            # Create event options with session_id
            event_options = EventOptions(user_id=user_id)
            if final_session_id:
                # Note: EventOptions might not support session_id directly
                # You may need to track a separate revenue event with session
                pass
                
            self._client.revenue(revenue_obj, event_options)
            logger.debug(f"Tracked revenue event for user {user_id}: ${amount} {currency} with session {final_session_id} on platform {platform} in {location.get('city', 'unknown') if location else 'unknown'}")
            
        except Exception as e:
            
            self._client.track(event)
            revenue_obj = Revenue(price=amount,
                      quantity=1,
                      product_id=product_id)
            
            # Create event options with session_id
            event_options = EventOptions(user_id=user_id)
            if final_session_id:
                # Note: EventOptions might not support session_id directly
                # You may need to track a separate revenue event with session
                pass
                
            self._client.revenue(revenue_obj, event_options)
            logger.debug(f"Tracked revenue event for user {user_id}: ${amount} {currency} with session {final_session_id} on platform {platform}")
            
        except Exception as e:
            logger.error(f"Failed to track revenue for user {user_id}: {str(e)}")

# Global instance
amplitude_service = AmplitudeService()

# Backward compatibility functions with session support
def track_event(user_id: str, event_type: str, event_properties: Optional[Dict[str, Any]] = None,
               session_id: Optional[str] = None, timestamp: Optional[str] = None, platform: Optional[str] = None,
               location: Optional[Dict[str, Any]] = None):
    """Backward compatible function for existing code."""
    amplitude_service.track_event(user_id, event_type, event_properties, session_id, timestamp, platform, location)

def identify_user(user_id: str, user_properties: Dict[str, Any]):
    """Update user properties."""
    amplitude_service.identify_user(user_id, user_properties)

def track_revenue(user_id: str, amount: float, currency: str = "USD", 
                 product_id: Optional[str] = None, additional_properties: Optional[Dict[str, Any]] = None,
                 session_id: Optional[str] = None, platform: Optional[str] = None, 
                 location: Optional[Dict[str, Any]] = None):
    """Track revenue events."""
    amplitude_service.track_revenue(user_id, amount, currency, product_id, additional_properties, session_id, platform, location)