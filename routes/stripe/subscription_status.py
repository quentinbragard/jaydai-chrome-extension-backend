# routes/stripe/subscription_status.py
from fastapi import HTTPException, Depends, Path
from . import router, stripe_service
from models.common import APIResponse
from models.stripe import SubscriptionStatusResponse
from utils.auth import get_current_user, require_user_access
import logging

logger = logging.getLogger(__name__)

@router.get("/subscription-status/{user_id}", response_model=APIResponse[SubscriptionStatusResponse])
async def get_subscription_status(
    user_id: str = Path(..., description="User ID to get subscription status for"),
    current_user: str = Depends(get_current_user)
):
    """Get the current subscription status for a user."""
    try:
        # Verify the user ID matches the authenticated user
        require_user_access(current_user, user_id)

        status = await stripe_service.get_subscription_status(user_id)
        return APIResponse(success=True, data=status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting subscription status: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving subscription status"
        )
