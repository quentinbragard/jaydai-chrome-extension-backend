# routes/stripe/subscription_status.py
from fastapi import HTTPException, Depends, Path
from . import router
from models.common import APIResponse
from models.stripe import SubscriptionStatusResponse
from utils.auth import get_current_user
from utils.stripe_config import stripe_config
import stripe
from datetime import datetime
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
        if user_id != current_user:
            raise HTTPException(status_code=403, detail="Unauthorized: Can only access your own subscription status")
        
        # Find the Stripe customer associated with this user
        try:
            customers = stripe.Customer.search(
                query=f"metadata['user_id']:'{user_id}'",
                limit=1,
            )
        except Exception as e:
            logger.error(f"Error searching Stripe customer for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve subscription status")

        if not customers.data:
            empty_status = SubscriptionStatusResponse(
                isActive=False,
                planId=None,
                currentPeriodEnd=None,
                cancelAtPeriodEnd=False,
                stripeCustomerId=None,
                stripeSubscriptionId=None,
            )
            return APIResponse(success=True, data=empty_status)

        customer = customers.data[0]

        try:
            subs = stripe.Subscription.list(customer=customer.id, status="all", limit=1)
        except Exception as e:
            logger.error(f"Error retrieving subscription for customer {customer.id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve subscription status")

        if not subs.data:
            empty_status = SubscriptionStatusResponse(
                isActive=False,
                planId=None,
                currentPeriodEnd=None,
                cancelAtPeriodEnd=False,
                stripeCustomerId=customer.id,
                stripeSubscriptionId=None,
            )
            return APIResponse(success=True, data=empty_status)

        subscription = subs.data[0]
        is_active = subscription.status in ["active", "trialing"]
        current_period_end = (
            datetime.fromtimestamp(subscription.current_period_end).isoformat()
            if subscription.current_period_end
            else None
        )

        status = SubscriptionStatusResponse(
            isActive=is_active,
            planId=subscription.metadata.get("plan_id"),
            currentPeriodEnd=current_period_end,
            cancelAtPeriodEnd=subscription.cancel_at_period_end or False,
            stripeCustomerId=customer.id,
            stripeSubscriptionId=subscription.id,
        )

        return APIResponse(success=True, data=status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting subscription status: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving subscription status"
        )