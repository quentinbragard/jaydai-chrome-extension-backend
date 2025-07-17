import os
import stripe
from typing import Optional
from utils.stripe_config import stripe_config


def _get_plan_id_from_price(price_id: str) -> Optional[str]:
    """Map a Stripe price ID to an internal plan identifier."""
    if price_id == stripe_config.monthly_price_id:
        return "monthly"
    if price_id == stripe_config.yearly_price_id:
        return "yearly"
    return None
