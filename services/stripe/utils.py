import os
import stripe
from typing import Optional
from utils.stripe_config import stripe_config


def _get_product_id_from_price(price_id: str) -> Optional[str]:
    """Map a Stripe price ID to an internal plan identifier."""
    if price_id == stripe_config.monthly_price_id:
        return "monthly"
    if price_id == stripe_config.yearly_price_id:
        return "yearly"
    return None

def _get_plan_name_from_product_id(product_id: str) -> Optional[str]:
    """Map a Stripe plan ID to an internal plan identifier."""
    if product_id == stripe_config.plus_product_id:
        return "plus"
    #if product_id == stripe_config.pro_product_id:
    #    return "pro"
    return "unknown"
