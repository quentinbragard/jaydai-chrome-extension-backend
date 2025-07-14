# routes/stripe/verify_session.py
from fastapi import HTTPException, Depends
from . import router, stripe_service
from models.stripe import VerifySessionRequest, VerifySessionResponse
from utils.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

@router.post("/verify-session", response_model=VerifySessionResponse)
async def verify_checkout_session(
    request: VerifySessionRequest,
    current_user: str = Depends(get_current_user)
):
    """Verify a checkout session and return subscription details."""
    try:
        result = await stripe_service.verify_checkout_session(request.sessionId)
        
        if not result["success"]:
            raise HTTPException(
                status_code=400, 
                detail=result.get("error", "Failed to verify checkout session")
            )
        
        return VerifySessionResponse(
            success=True,
            subscription=result.get("subscription")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error verifying session: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while verifying checkout session"
        )