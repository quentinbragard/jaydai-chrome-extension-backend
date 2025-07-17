# services/stripe/stripe_config.py
import os
import stripe
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class StripeConfig:
    def __init__(self):
        self.secret_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        self.monthly_price_id = os.getenv("STRIPE_PLUS_MONTHLY_PRICE_ID")
        self.yearly_price_id = os.getenv("STRIPE_PLUS_YEARLY_PRICE_ID")
        self.plus_product_id = os.getenv("STRIPE_PLUS_PRODUCT_ID")
        
        if not self.secret_key:
            raise ValueError("STRIPE_SECRET_KEY environment variable is required")
        
        stripe.api_key = self.secret_key
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self):
        """Validate that all required Stripe configuration is present."""
        required_vars = {
            "STRIPE_SECRET_KEY": self.secret_key,
            "STRIPE_WEBHOOK_SECRET": self.webhook_secret,
            "STRIPE_PLUS_MONTHLY_PRICE_ID": self.monthly_price_id,
            "STRIPE_PLUS_YEARLY_PRICE_ID": self.yearly_price_id,
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        
        if missing_vars:
            logger.warning(f"Missing Stripe configuration: {', '.join(missing_vars)}")
            # Don't raise error for webhook secret as it might not be needed in all environments
            required_for_operation = ["STRIPE_SECRET_KEY", "STRIPE_PLUS_MONTHLY_PRICE_ID", "STRIPE_PLUS_YEARLY_PRICE_ID"]
            missing_required = [var for var in missing_vars if var in required_for_operation]
            
            if missing_required:
                raise ValueError(f"Required Stripe configuration missing: {', '.join(missing_required)}")
    
    @property
    def pricing_plans(self) -> Dict[str, Dict[str, Any]]:
        """Get configured pricing plans."""
        return {
            "monthly": {
                "id": "monthly",
                "name": "Monthly Plan",
                "price": 8.99,
                "currency": "EUR",
                "interval": "month",
                "priceId": self.monthly_price_id
            },
            "yearly": {
                "id": "yearly", 
                "name": "Yearly Plan",
                "price": 6.99,  # Per month when billed yearly
                "currency": "EUR",
                "interval": "year",
                "priceId": self.yearly_price_id
            }
        }
        

# Global instance
stripe_config = StripeConfig()