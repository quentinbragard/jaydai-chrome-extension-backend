# routes/stripe/cancel_subscription.py
from fastapi import HTTPException, Depends
from . import router, stripe_service
from models.stripe import CancelSubscriptionRequest
from utils.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

@router.post("/cancel-subscription")
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    current_user: str = Depends(get_current_user)
):
    """Cancel a user's subscription."""
    try:
        # Verify the user ID matches the authenticated user
        if request.userId != current_user:
            raise HTTPException(status_code=403, detail="Unauthorized: User ID mismatch")
        
        success = await stripe_service.cancel_subscription(request.userId)
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail="Failed to cancel subscription. Please ensure you have an active subscription."
            )
        
        return {
            "success": True,
            "message": "Subscription cancelled successfully. It will remain active until the end of your billing period."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error cancelling subscription: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while cancelling subscription"
        )