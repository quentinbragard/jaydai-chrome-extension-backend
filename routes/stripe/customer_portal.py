# routes/stripe/customer_portal.py
from fastapi import HTTPException, Depends
from . import router, stripe_service
from models.stripe import CustomerPortalRequest, CustomerPortalResponse
from utils.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

@router.post("/customer-portal", response_model=CustomerPortalResponse)
async def create_customer_portal(
    request: CustomerPortalRequest,
    current_user: str = Depends(get_current_user)
):
    """Create a customer portal session for subscription management."""
    try:
        # Verify the user ID matches the authenticated user
        if request.userId != current_user:
            raise HTTPException(status_code=403, detail="Unauthorized: User ID mismatch")
        
        portal_url = await stripe_service.create_customer_portal_session(
            user_id=request.userId,
            return_url=request.returnUrl
        )
        
        if not portal_url:
            raise HTTPException(
                status_code=400, 
                detail="Failed to create customer portal session. Please ensure you have an active subscription."
            )
        
        return CustomerPortalResponse(
            success=True,
            url=portal_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating customer portal: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while creating customer portal session"
        )