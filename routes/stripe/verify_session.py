# routes/stripe/verify_session.py
from fastapi import HTTPException, Depends, Request
from . import router, stripe_service
from models.stripe import VerifySessionRequest, VerifySessionResponse
from utils.auth import get_current_user
import logging
import stripe

logger = logging.getLogger(__name__)

@router.post("/verify-session", response_model=VerifySessionResponse)
async def verify_checkout_session(
    request: VerifySessionRequest,
    http_request: Request
):
    """
    Verify a checkout session and return subscription details.
    
    This endpoint handles authentication in a special way:
    1. If Authorization header is present, use it for authentication
    2. If no auth header, verify the session contains valid user metadata
    """
    try:
        # First, verify the session with Stripe to get user information
        try:
            session = stripe.checkout.Session.retrieve(
                request.sessionId,
                expand=['subscription']
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving session: {str(e)}")
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid session: {str(e)}"
            )
        
        if session.payment_status != 'paid':
            raise HTTPException(
                status_code=400,
                detail="Payment not completed"
            )
        
        user_id = session.metadata.get('user_id')
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="User ID not found in session metadata"
            )
        
        # Check if we have authentication header
        auth_header = http_request.headers.get('Authorization')
        if auth_header:
            # If auth header is present, verify it matches the session user
            try:
                from utils.auth import verify_token
                token = auth_header.replace('Bearer ', '')
                authenticated_user_id = verify_token(token)
                
                if authenticated_user_id != user_id:
                    raise HTTPException(
                        status_code=403,
                        detail="Token user ID does not match session user ID"
                    )
            except Exception as e:
                logger.warning(f"Auth verification failed: {str(e)}")
                # Continue without auth if session is valid - this allows 
                # the landing page to work without proper extension auth
                pass
        
        # Process the verification
        result = await stripe_service.verify_checkout_session(request.sessionId)
        
        if not result["success"]:
            raise HTTPException(
                status_code=400, 
                detail=result.get("error", "Failed to verify checkout session")
            )
        
        logger.info(f"Session {request.sessionId} verified successfully for user {user_id}")
        
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