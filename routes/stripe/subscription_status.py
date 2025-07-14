# routes/stripe/subscription_status.py
from fastapi import HTTPException, Depends, Path
from . import router, stripe_service
from models.stripe import SubscriptionStatusResponse
from utils.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

@router.get("/subscription-status/{user_id}", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    user_id: str = Path(..., description="User ID to get subscription status for"),
    current_user: str = Depends(get_current_user)
):
    """Get the current subscription status for a user."""
    try:
        # Verify the user ID matches the authenticated user
        if user_id != current_user:
            raise HTTPException(status_code=403, detail="Unauthorized: Can only access your own subscription status")
        
        subscription_status = await stripe_service.get_subscription_status(user_id)
        return subscription_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting subscription status: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving subscription status"
        )