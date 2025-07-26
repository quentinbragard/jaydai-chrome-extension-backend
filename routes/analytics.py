# routes/analytics.py - Updated with automatic IP-based location detection

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from utils.amplitude import amplitude_service
from utils import supabase_helpers
from utils.geolocation import get_location_from_request
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

class AnalyticsEvent(BaseModel):
    event_name: str = Field(..., description="Name of the event")
    event_properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Event properties")
    user_id: Optional[str] = Field(None, description="User ID (optional if authenticated)")
    timestamp: Optional[str] = Field(None, description="Event timestamp (ISO format)")
    session_id: Optional[str] = Field(None, description="Session ID")
    platform: Optional[str] = Field("chrome_extension", description="Platform identifier")
    extension_version: Optional[str] = Field(None, description="Extension version")
    location: Optional[Dict[str, Any]] = Field(None, description="Location information")

class LocationInfo(BaseModel):
    country: Optional[str] = None
    region: Optional[str] = None  
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    ip: Optional[str] = None

class AnalyticsBatch(BaseModel):
    events: List[AnalyticsEvent] = Field(..., description="List of events to track")
    user_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="User context data")

class AnalyticsResponse(BaseModel):
    success: bool
    events_processed: int
    message: Optional[str] = None
    errors: Optional[List[str]] = None

@router.post("/track", response_model=AnalyticsResponse)
async def track_event(
    event: AnalyticsEvent,
    request: Request,
    user_id = Depends(supabase_helpers.get_user_from_session_token)
):
    """
    Track a single analytics event with proper session handling.
    """
    try:
        # Use the user_id from the event if provided, otherwise from auth
        final_user_id = event.user_id or user_id
        
        # If no user_id available, create an anonymous one based on session
        if not final_user_id:
            final_user_id = f"anonymous_{event.session_id or 'unknown'}"
       
        # Enrich event properties with context (but NOT session_id and timestamp)
        enhanced_properties = {
            **(event.event_properties or {}),
            "platform": event.platform or "chrome_extension",
            "extension_version": event.extension_version,
            "source": "chrome_extension",
            "client_ip": str(request.client.host) if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "is_authenticated": user_id is not None
        }

        # Get location from request IP (no additional permissions needed)
        request_location = get_location_from_request(request)
        print(f"Request location======================>>>: {request_location}")
        
        # Use client-provided location if available, otherwise use IP-based location
        final_location = event.location or request_location
        
        # Track in Amplitude with session_id, timestamp, platform, and location as separate parameters
        amplitude_service.track_event(
            user_id=final_user_id,
            event_type=event.event_name,
            event_properties=enhanced_properties,
            session_id=event.session_id,  # Pass session_id separately (will be converted to int)
            timestamp=event.timestamp,    # Pass timestamp separately
            platform=event.platform,      # Pass platform separately
            location=final_location        # Pass location separately (IP-based if not provided)
        )

        logger.info(f"Analytics event tracked: {event.event_name} for user {final_user_id} with session {event.session_id}")

        return AnalyticsResponse(
            success=True,
            events_processed=1,
            message="Event tracked successfully"
        )

    except Exception as e:
        logger.error(f"Failed to track analytics event: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to track event: {str(e)}")

@router.post("/track-batch", response_model=AnalyticsResponse)
async def track_events_batch(
    batch: AnalyticsBatch,
    request: Request,
    user_id = Depends(supabase_helpers.get_user_from_session_token)
):
    """
    Track multiple analytics events in a batch with proper session handling.
    """
    try:
        processed_count = 0
        errors = []
        
        for idx, event in enumerate(batch.events):
            try:
                # Use event user_id, auth user_id, or create anonymous ID
                final_user_id = event.user_id or user_id
                if not final_user_id:
                    final_user_id = f"anonymous_{event.session_id or idx}"

                # Enrich event properties (excluding session_id and timestamp)
                enhanced_properties = {
                    **(event.event_properties or {}),
                    **(batch.user_context or {}),
                    "platform": event.platform or "chrome_extension",
                    "extension_version": event.extension_version,
                    "source": "chrome_extension",
                    "client_ip": str(request.client.host) if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                    "is_authenticated": user_id is not None,
                    "batch_index": idx
                }

                # Get location from request IP for this event
                event_location = event.location or get_location_from_request(request)
                print(f"Event location======================>>>: {event_location}")

                # Track in Amplitude with proper session handling
                amplitude_service.track_event(
                    user_id=final_user_id,
                    event_type=event.event_name,
                    event_properties=enhanced_properties,
                    session_id=event.session_id,  # Pass session_id separately (will be converted to int)
                    timestamp=event.timestamp,    # Pass timestamp separately
                    platform=event.platform,      # Pass platform separately
                    location=event_location        # Pass location separately (IP-based if not provided)
                )

                processed_count += 1

            except Exception as event_error:
                error_msg = f"Event {idx} ({event.event_name}): {str(event_error)}"
                errors.append(error_msg)
                logger.error(f"Failed to process event in batch: {error_msg}")

        logger.info(f"Analytics batch processed: {processed_count}/{len(batch.events)} events")

        return AnalyticsResponse(
            success=processed_count > 0,
            events_processed=processed_count,
            message=f"Processed {processed_count} out of {len(batch.events)} events",
            errors=errors if errors else None
        )

    except Exception as e:
        logger.error(f"Failed to process analytics batch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process batch: {str(e)}")

@router.post("/identify")
async def identify_user(
    user_properties: Dict[str, Any],
    request: Request,
    user_id = Depends(supabase_helpers.get_user_from_session_token)
):
    """
    Update user properties in analytics.
    """
    try:
        # Must be authenticated for identify calls
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required for user identification")
        
        # Enrich user properties
        enhanced_properties = {
            **user_properties,
            "last_seen": datetime.utcnow().isoformat(),
            "platform": "chrome_extension",
            "client_ip": str(request.client.host) if request.client else None
        }

        # Update in Amplitude
        amplitude_service.identify_user(user_id, enhanced_properties)

        logger.info(f"User identified: {user_id}")

        return {
            "success": True,
            "message": "User properties updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to identify user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to identify user: {str(e)}")

@router.get("/health")
async def analytics_health():
    """
    Check analytics service health.
    """
    try:
        # Check if Amplitude is configured
        has_amplitude = amplitude_service._client is not None
        
        return {
            "status": "healthy" if has_amplitude else "degraded",
            "amplitude_configured": has_amplitude,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Analytics health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }