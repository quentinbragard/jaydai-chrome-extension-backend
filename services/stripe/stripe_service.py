import stripe
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from supabase import Client
from .stripe_config import stripe_config
from models.stripe import SubscriptionStatusResponse
import os
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)

def retry_on_stripe_error(max_retries=3, delay=1):
    """Decorator to retry Stripe API calls on certain errors."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except stripe.error.RateLimitError as e:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(delay * (2 ** attempt))
                except stripe.error.APIConnectionError as e:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(delay)
                except stripe.error.StripeError as e:
                    raise
            return None
        return wrapper
    return decorator

class StripeService:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.config = stripe_config
        self._webhook_event_cache = {}

    async def get_subscription_status(self, user_id: str) -> SubscriptionStatusResponse:
        """Get user's current subscription status from stripe_subscriptions table."""
        try:
            # Get subscription from stripe_subscriptions table
            subscription_response = self.supabase.table("stripe_subscriptions").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).limit(1).execute()
            
            # Get user metadata separately
            user_metadata_response = self.supabase.table("users_metadata").select(
                "subscription_plan"
            ).eq("user_id", user_id).single().execute()
            
            if not subscription_response.data:
                # No subscription found
                return SubscriptionStatusResponse(
                    isActive=False,
                    planId=user_metadata_response.data.get("subscription_plan") if user_metadata_response.data else None,
                    currentPeriodEnd=None,
                    cancelAtPeriodEnd=False,
                    stripeCustomerId=None,
                    stripeSubscriptionId=None
                )
            
            subscription = subscription_response.data[0]
            plan_id = user_metadata_response.data.get("subscription_plan") if user_metadata_response.data else None
            
            # Verify with Stripe if subscription exists
            try:
                stripe_subscription = stripe.Subscription.retrieve(subscription["stripe_subscription_id"])
                
                # Check if local status differs from Stripe
                if subscription["status"] != stripe_subscription.status:
                    logger.info(f"Subscription status mismatch for user {user_id}: "
                              f"local={subscription['status']}, stripe={stripe_subscription.status}")
                    await self._update_subscription_status(user_id, stripe_subscription)
                    subscription["status"] = stripe_subscription.status
                
                is_active = stripe_subscription.status in ['active', 'trialing']
                
                return SubscriptionStatusResponse(
                    isActive=is_active,
                    planId=plan_id,
                    currentPeriodEnd=subscription["current_period_end"],
                    cancelAtPeriodEnd=subscription["cancel_at_period_end"],
                    stripeCustomerId=subscription["stripe_customer_id"],
                    stripeSubscriptionId=subscription["stripe_subscription_id"]
                )
                
            except stripe.error.StripeError as e:
                logger.warning(f"Failed to retrieve subscription from Stripe: {str(e)}")
                
                # Return local status
                is_active = subscription["status"] in ['active', 'trialing']
                return SubscriptionStatusResponse(
                    isActive=is_active,
                    planId=plan_id,
                    currentPeriodEnd=subscription["current_period_end"],
                    cancelAtPeriodEnd=subscription["cancel_at_period_end"],
                    stripeCustomerId=subscription["stripe_customer_id"],
                    stripeSubscriptionId=subscription["stripe_subscription_id"]
                )
            
        except Exception as e:
            logger.error(f"Error getting subscription status for user {user_id}: {str(e)}")
            return SubscriptionStatusResponse(
                isActive=False,
                planId=None,
                currentPeriodEnd=None,
                cancelAtPeriodEnd=False,
                stripeCustomerId=None,
                stripeSubscriptionId=None
            )

    async def _update_subscription_status(self, user_id: str, subscription: stripe.Subscription, stripe_event_id: Optional[str] = None):
        """Update subscription status in both tables."""
        try:
            # Determine the plan ID
            product_id = subscription.get('items').get('data')[0].get('plan').get('product')
            if product_id == self.config.plus_product_id:
                subscription_plan = "plus"
            else:
                subscription_plan = None
            
            # Update users_metadata table (simplified)
            self.supabase.table("users_metadata").update({
                "subscription_status": subscription.status,
                "subscription_plan": subscription_plan,
                "stripe_customer_id": subscription.customer,
            }).eq("user_id", user_id).execute()
            
            # Update or create stripe_subscriptions record
            subscription_data = {
                "user_id": user_id,
                "stripe_customer_id": subscription.customer,
                "stripe_subscription_id": subscription.id,
                "stripe_price_id": subscription.get('items').get('data')[0].get('price').get('id'),
                "stripe_product_id": product_id,
                "status": subscription.status,
                "current_period_start": datetime.fromtimestamp(subscription.current_period_start).isoformat(),
                "current_period_end": datetime.fromtimestamp(subscription.current_period_end).isoformat(),
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "cancelled_at": datetime.fromtimestamp(subscription.canceled_at).isoformat() if subscription.canceled_at else None,
                "trial_start": datetime.fromtimestamp(subscription.trial_start).isoformat() if subscription.trial_start else None,
                "trial_end": datetime.fromtimestamp(subscription.trial_end).isoformat() if subscription.trial_end else None,
                "metadata": subscription.metadata or {}
            }
            
            # Try to update existing record first
            existing_subscription = self.supabase.table("stripe_subscriptions").select("id").eq(
                "stripe_subscription_id", subscription.id
            ).execute()
            
            if existing_subscription.data:
                self.supabase.table("stripe_subscriptions").update(subscription_data).eq(
                    "stripe_subscription_id", subscription.id
                ).execute()
            else:
                self.supabase.table("stripe_subscriptions").insert(subscription_data).execute()
            
            logger.info(f"Updated subscription status for user {user_id}: {subscription.status}")
            
        except Exception as e:
            logger.error(f"Failed to update subscription status for user {user_id}: {str(e)}")

    async def cancel_subscription(self, user_id: str) -> bool:
        """Cancel user's subscription."""
        try:
            # Get user's subscription
            subscription_response = self.supabase.table("stripe_subscriptions").select(
                "stripe_subscription_id"
            ).eq("user_id", user_id).eq("status", "active").or_("status.eq.trialing").execute()
            
            if not subscription_response.data:
                logger.warning(f"No active subscription found for user {user_id}")
                return False
            
            subscription_id = subscription_response.data[0]["stripe_subscription_id"]
            
            # Cancel subscription at period end
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            
            # Update database
            await self._update_subscription_status(user_id, subscription)
            
            logger.info(f"Cancelled subscription {subscription_id} for user {user_id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error cancelling subscription: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error cancelling subscription: {str(e)}")
            return False

    async def reactivate_subscription(self, user_id: str) -> bool:
        """Reactivate a cancelled subscription."""
        try:
            # Get user's subscription
            subscription_response = self.supabase.table("stripe_subscriptions").select(
                "stripe_subscription_id"
            ).eq("user_id", user_id).eq("cancel_at_period_end", True).execute()
            
            if not subscription_response.data:
                logger.warning(f"No cancelled subscription found for user {user_id}")
                return False
            
            subscription_id = subscription_response.data[0]["stripe_subscription_id"]
            
            # Reactivate subscription
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False
            )
            
            # Update database
            await self._update_subscription_status(user_id, subscription)
            
            logger.info(f"Reactivated subscription {subscription_id} for user {user_id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error reactivating subscription: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error reactivating subscription: {str(e)}")
            return False

    async def get_detailed_subscription_info(self, user_id: str) -> Dict[str, Any]:
        """Get detailed subscription information for display."""
        try:
            # Get subscription data
            subscription_response = self.supabase.table("stripe_subscriptions").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).limit(1).execute()
            
            # Get user metadata
            user_metadata_response = self.supabase.table("users_metadata").select(
                "subscription_plan, name, email"
            ).eq("user_id", user_id).single().execute()
            
            if not subscription_response.data:
                return {
                    "hasSubscription": False,
                    "status": "inactive",
                    "planId": user_metadata_response.data.get("subscription_plan") if user_metadata_response.data else None
                }
            
            subscription = subscription_response.data[0]
            user_metadata = user_metadata_response.data or {}
            
            return {
                "hasSubscription": True,
                "status": subscription["status"],
                "planId": user_metadata.get("subscription_plan"),
                "currentPeriodStart": subscription["current_period_start"],
                "currentPeriodEnd": subscription["current_period_end"],
                "cancelAtPeriodEnd": subscription["cancel_at_period_end"],
                "cancelledAt": subscription.get("cancelled_at"),
                "trialStart": subscription.get("trial_start"),
                "trialEnd": subscription.get("trial_end"),
                "isTrialing": subscription["status"] == "trialing",
                "isActive": subscription["status"] in ["active", "trialing"],
                "isPastDue": subscription["status"] == "past_due",
                "isCancelled": subscription["status"] == "cancelled" or subscription["cancel_at_period_end"],
                "stripeCustomerId": subscription["stripe_customer_id"],
                "stripeSubscriptionId": subscription["stripe_subscription_id"]
            }
            
        except Exception as e:
            logger.error(f"Error getting detailed subscription info for user {user_id}: {str(e)}")
            return {
                "hasSubscription": False,
                "status": "inactive",
                "planId": None
            }

    async def create_checkout_session(
        self, 
        price_id: str, 
        user_id: str, 
        auth_token: str,
        user_email: str, 
        success_url: str, 
        cancel_url: str
    ) -> Dict[str, Any]:
        """Create a Stripe checkout session with enhanced error handling."""
        try:
            # Check if user already has an active subscription
            existing_subscription = await self.get_subscription_status(user_id)
            if existing_subscription.isActive:
                return {
                    "success": False,
                    "error": "User already has an active subscription"
                }
            
            # Get or create customer
            customer = await self._get_or_create_customer(user_id, user_email)
            
            # Determine plan identifier
            plan_id = self._get_plan_id_from_price(price_id)
            
            # Create metadata
            metadata = {
                "user_id": user_id,
                "auth_token": auth_token[:50] if auth_token else "",
                "created_via": "chrome_extension"
            }
            if plan_id:
                metadata["plan_id"] = plan_id

            # Configure success URL
            is_prod = os.getenv("ENVIRONMENT") == "prod"
            success_url_suffix = f'&session_id={{CHECKOUT_SESSION_ID}}'
            if auth_token:
                success_url_suffix += f'&auth_token={auth_token}'
            if not is_prod:
                success_url_suffix += '&dev=true'
            
            # Create checkout session with trial period if applicable
            session_params = {
                "customer": customer.id,
                "payment_method_types": ['card'],
                "line_items": [{
                    'price': price_id,
                    'quantity': 1,
                }],
                "mode": 'subscription',
                "success_url": success_url + success_url_suffix,
                "cancel_url": cancel_url,
                "metadata": metadata,
                "subscription_data": {
                    'metadata': metadata,
                    'trial_period_days': 7
                },
                "allow_promotion_codes": True,
                "billing_address_collection": "auto",
                "customer_update": {
                    "address": "auto",
                    "name": "auto"
                }
            }
            
            session = stripe.checkout.Session.create(**session_params)
            
            logger.info(f"Created checkout session {session.id} for user {user_id}")
            
            return {
                "success": True,
                "sessionId": session.id,
                "url": session.url
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {str(e)}")
            return {
                "success": False,
                "error": f"Payment service error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error creating checkout session: {str(e)}")
            return {
                "success": False,
                "error": "An unexpected error occurred"
            }

    async def _get_or_create_customer(self, user_id: str, user_email: str) -> stripe.Customer:
        """Get existing Stripe customer or create a new one."""
        # Check if customer exists in database
        user_response = self.supabase.table("users_metadata").select(
            "stripe_customer_id, name"
        ).eq("user_id", user_id).single().execute()
        
        customer_id = user_response.data.get("stripe_customer_id") if user_response.data else None
        
        if customer_id:
            try:
                return stripe.Customer.retrieve(customer_id)
            except stripe.error.StripeError:
                logger.warning(f"Stripe customer {customer_id} not found, creating new one")
        
        # Create new customer
        customer_name = user_response.data.get("name") if user_response.data else None
        customer = stripe.Customer.create(
            email=user_email,
            name=customer_name,
            metadata={
                'user_id': user_id
            }
        )
        
        # Update database with customer ID
        self.supabase.table("users_metadata").update({
            "stripe_customer_id": customer.id
        }).eq("user_id", user_id).execute()
        
        logger.info(f"Created new Stripe customer {customer.id} for user {user_id}")
        return customer

    def _get_plan_id_from_price(self, price_id: str) -> Optional[str]:
        """Get plan ID from price ID."""
        if price_id == self.config.monthly_price_id:
            return "monthly"
        elif price_id == self.config.yearly_price_id:
            return "yearly"
        return None

    async def create_customer_portal_session(self, user_id: str, return_url: str) -> Optional[str]:
        """Create a customer portal session for subscription management."""
        try:
            # Get user's Stripe customer ID
            user_response = self.supabase.table("users_metadata").select(
                "stripe_customer_id"
            ).eq("user_id", user_id).single().execute()
            
            if not user_response.data or not user_response.data.get("stripe_customer_id"):
                logger.warning(f"No Stripe customer found for user {user_id}")
                return None
            
            customer_id = user_response.data["stripe_customer_id"]
            
            # Create portal session
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            
            logger.info(f"Created customer portal session for user {user_id}")
            return session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer portal: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating customer portal: {str(e)}")
            return None

    async def verify_checkout_session(self, session_id: str) -> Dict[str, Any]:
        """Verify a checkout session and return subscription details."""
        try:
            session = stripe.checkout.Session.retrieve(
                session_id,
                expand=['subscription']
            )
            
            if session.payment_status != 'paid':
                return {
                    "success": False,
                    "error": "Payment not completed"
                }
            
            user_id = session.metadata.get('user_id')
            if not user_id:
                return {
                    "success": False,
                    "error": "User ID not found in session metadata"
                }
            
            # Update subscription status in database
            if session.subscription:
                await self._update_subscription_status(user_id, session.subscription)
            
            # Get updated subscription status
            subscription_status = await self.get_subscription_status(user_id)
            
            return {
                "success": True,
                "subscription": subscription_status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error verifying session: {str(e)}")
            return {
                "success": False,
                "error": f"Payment verification failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error verifying session: {str(e)}")
            return {
                "success": False,
                "error": "An unexpected error occurred"
            }

    # Webhook handling methods remain the same...
    async def handle_webhook_event(self, event: Dict[str, Any]) -> bool:
        """Enhanced webhook handler with idempotency and better error handling."""
        event_id = event.get("id")
        event_type = event.get("type")
        event_data = event.get("data", {})
        
        # Check if we've already processed this event
        if event_id in self._webhook_event_cache:
            logger.info(f"Skipping already processed event {event_id}")
            return True
        
        # Check database for existing event
        existing_event = self.supabase.table("stripe_webhook_events").select(
            "id, processed"
        ).eq("stripe_event_id", event_id).maybe_single().execute()
        
        if existing_event and existing_event.data and existing_event.data.get("processed"):
            logger.info(f"Event {event_id} already processed")
            self._webhook_event_cache[event_id] = True
            return True
        
        # Record the event
        record_id = await self._record_webhook_event(event_id, event_type, event_data)
        
        try:
            success = await self._process_webhook_event(event_id, event_type, event_data)
            
            # Update event as processed
            if record_id:
                self.supabase.table("stripe_webhook_events").update({
                    "processed": success,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", record_id).execute()
            
            # Cache the result
            self._webhook_event_cache[event_id] = success
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing webhook event {event_type}: {str(e)}")
            
            # Mark as failed
            if record_id:
                self.supabase.table("stripe_webhook_events").update({
                    "processed": False,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", record_id).execute()
            
            return False

    async def _record_webhook_event(self, event_id: str, event_type: str, event_data: Dict[str, Any]) -> Optional[str]:
        """Persist webhook event payload in the database."""
        try:
            response = self.supabase.table("stripe_webhook_events").insert({
                "stripe_event_id": event_id,
                "event_type": event_type,
                "event_data": event_data,
            }).execute()
            if response.data:
                return response.data[0]["id"]
        except Exception as e:
            logger.error(f"Failed to record webhook event {event_id}: {e}")
        return None

    async def _process_webhook_event(self, event_id: str, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Process different types of webhook events."""
        handlers = {
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_succeeded": self._handle_payment_succeeded,
            "invoice.payment_failed": self._handle_payment_failed,
        }
        
        handler = handlers.get(event_type)
        if handler:
            return await handler(event_id, event_data.get("object", {}))
        else:
            logger.info(f"No handler for event type: {event_type}")
            return True

    async def _handle_subscription_created(self, event_id: str, subscription: Dict[str, Any]):
        """Handle subscription created event."""
        user_id = subscription["metadata"].get("user_id")
        if user_id:
            stripe_subscription = stripe.Subscription.construct_from(subscription, stripe.api_key)
            await self._update_subscription_status(user_id, stripe_subscription, event_id)

    async def _handle_subscription_updated(self, event_id: str, subscription: Dict[str, Any]):
        """Handle subscription updated event."""
        user_id = subscription["metadata"].get("user_id")
        if user_id:
            stripe_subscription = stripe.Subscription.construct_from(subscription, stripe.api_key)
            await self._update_subscription_status(user_id, stripe_subscription, event_id)

    async def _handle_subscription_deleted(self, event_id: str, subscription: Dict[str, Any]):
        """Handle subscription deleted event."""
        user_id = subscription["metadata"].get("user_id")
        if user_id:
            # Update both tables
            self.supabase.table("users_metadata").update({
                "subscription_status": "cancelled",
                "subscription_plan": None
            }).eq("user_id", user_id).execute()
            
            self.supabase.table("stripe_subscriptions").update({
                "status": "cancelled",
                "cancelled_at": datetime.now(timezone.utc).isoformat()
            }).eq("user_id", user_id).execute()
            
            logger.info(f"Marked subscription as cancelled for user {user_id}")

    async def _handle_payment_succeeded(self, event_id: str, invoice: Dict[str, Any]):
        """Handle successful payment."""
        subscription_id = invoice.get("subscription")
        if subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user_id = subscription.metadata.get("user_id")
                if user_id:
                    await self._update_subscription_status(user_id, subscription, event_id)
                return True
            except stripe.error.StripeError as e:
                logger.error(f"Failed to retrieve subscription {subscription_id}: {str(e)}")
                return False
        return True

    async def _handle_payment_failed(self, event_id: str, invoice: Dict[str, Any]):
        """Handle failed payment."""
        subscription_id = invoice.get("subscription")
        if subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user_id = subscription.metadata.get("user_id")
                if user_id:
                    await self._update_subscription_status(user_id, subscription, event_id)
            except stripe.error.StripeError as e:
                logger.error(f"Failed to retrieve subscription {subscription_id}: {str(e)}")
        return True