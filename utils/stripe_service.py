import logging
from typing import Dict, Any, Optional
from supabase import Client

from services.stripe import checkout, portal, subscriptions, webhooks, customer
from models.stripe import SubscriptionStatusResponse

logger = logging.getLogger(__name__)


class StripeService:
    """Lightweight wrapper delegating to stripe helper modules."""

    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    async def get_subscription_status(self, user_id: str) -> SubscriptionStatusResponse:
        return await subscriptions.get_subscription_status(self.supabase, user_id)

    async def cancel_subscription(self, user_id: str) -> bool:
        return await subscriptions.cancel_subscription(self.supabase, user_id)

    async def reactivate_subscription(self, user_id: str) -> bool:
        return await subscriptions.reactivate_subscription(self.supabase, user_id)

    async def create_checkout_session(
        self,
        price_id: str,
        user_id: str,
        auth_token: str,
        user_email: str,
        success_url: str,
        cancel_url: str,
        redirect_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await checkout.create_checkout_session(
            self.supabase,
            price_id,
            user_id,
            auth_token,
            user_email,
            success_url,
            cancel_url,
            redirect_url,
        )

    async def verify_checkout_session(self, session_id: str) -> Dict[str, Any]:
        return await checkout.verify_checkout_session(self.supabase, session_id)

    async def create_customer_portal_session(self, user_id: str, return_url: str) -> Optional[str]:
        return await portal.create_customer_portal_session(self.supabase, user_id, return_url)

    async def handle_webhook_event(self, event: Dict[str, Any]) -> bool:
        return await webhooks.handle_webhook_event(self.supabase, event)

    async def ensure_stripe_customer(self, user_id: str, user_email: str):
        return await customer.ensure_stripe_customer(self.supabase, user_id, user_email)
