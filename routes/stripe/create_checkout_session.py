# routes/stripe/create_checkout_session.py - UUID Corrected
from fastapi import HTTPException, Depends
from urllib.parse import urlparse
from . import router, stripe_service
from models.stripe import CreateCheckoutSessionRequest, CreateCheckoutSessionResponse
from utils.auth import get_current_user, require_user_access
import logging

logger = logging.getLogger(__name__)

@router.post("/create-checkout-session", response_model=CreateCheckoutSessionResponse)
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user: str = Depends(get_current_user)
):
    """Create a Stripe checkout session for subscription payment."""
    try:
        # Verify the user ID matches the authenticated user
        require_user_access(current_user, request.userId)


        result = await stripe_service.create_checkout_session(
            price_id=request.priceId,
            user_id=request.userId,
            user_email=request.userEmail,
            success_url=request.successUrl,
            cancel_url=request.cancelUrl
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400, 
                detail=result.get("error", "Failed to create checkout session")
            )
        
        return CreateCheckoutSessionResponse(
            success=True,
            sessionId=result["sessionId"],
            url=result["url"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while creating checkout session"
        )