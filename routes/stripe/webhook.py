# routes/stripe/webhooks.py
from fastapi import HTTPException, Request, Header
from . import router, stripe_service
import stripe
import json
import logging
from utils.stripe_config import stripe_config

logger = logging.getLogger(__name__)

@router.post("/webhook")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    """Handle Stripe webhook events."""
    try:
        # Get the raw body
        body = await request.body()
        print("body", body)
        
        if not stripe_signature:
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")
        
        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                body, 
                stripe_signature, 
                stripe_config.webhook_secret
            )
        except ValueError:
            logger.error("Invalid payload in webhook")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid signature in webhook")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Handle the event
        event_type = event['type']
        event_data = event['data']
        
        logger.info(f"Received webhook event: {event_type}")
        
        # Process the event
        success = await stripe_service.handle_webhook_event(event_type, event_data)
        
        if not success:
            logger.error(f"Failed to process webhook event: {event_type}")
            raise HTTPException(status_code=500, detail="Failed to process webhook event")
        
        return {"success": True, "received": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in webhook handler: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while processing webhook"
        )