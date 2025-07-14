# routes/stripe/pricing.py
from fastapi import HTTPException
from . import router
from models.stripe import PricingResponse, PricingPlan
from utils.stripe_config import stripe_config
import logging

logger = logging.getLogger(__name__)

@router.get("/pricing", response_model=PricingResponse)
async def get_pricing():
    """Get available pricing plans."""
    try:
        plans_config = stripe_config.pricing_plans
        
        plans = [
            PricingPlan(
                id=plan_data["id"],
                name=plan_data["name"],
                price=plan_data["price"],
                currency=plan_data["currency"],
                interval=plan_data["interval"],
                priceId=plan_data["priceId"]
            )
            for plan_data in plans_config.values()
        ]
        
        return PricingResponse(
            success=True,
            plans=plans
        )
        
    except Exception as e:
        logger.error(f"Unexpected error getting pricing: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving pricing information"
        )