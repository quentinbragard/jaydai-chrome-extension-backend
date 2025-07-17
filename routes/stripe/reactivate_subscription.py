# routes/stripe/reactivate_subscription.py
from fastapi import HTTPException, Depends
from . import router, stripe_service
from utils.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

@router.post("/reactivate-subscription")
async def reactivate_subscription(
    current_user: str = Depends(get_current_user)
):
    """Reactivate a cancelled subscription."""
    try:
        success = await stripe_service.reactivate_subscription(current_user)
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail="Failed to reactivate subscription. Please ensure you have a cancelled subscription that hasn't expired."
            )
        
        return {
            "success": True,
            "message": "Subscription reactivated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error reactivating subscription: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while reactivating subscription"
        )