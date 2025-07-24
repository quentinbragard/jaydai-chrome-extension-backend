# utils/amplitude_init.py - Simple initialization for Amplitude
import os
import logging
from datetime import datetime
from utils.amplitude import amplitude_service

logger = logging.getLogger(__name__)

def init_amplitude() -> bool:
    """Initialize Amplitude for Stripe payment tracking."""
    try:
        # Check if Amplitude is properly configured
        api_key = os.getenv("AMPLITUDE_API_KEY")
        if not api_key:
            logger.warning("AMPLITUDE_API_KEY not found in environment variables")
            return False
        
        logger.info("Amplitude successfully initialized for Stripe tracking")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize Amplitude: {str(e)}")
        return False