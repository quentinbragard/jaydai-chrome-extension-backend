# Enhanced stripe_service.py improvements
import stripe
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from supabase import Client
from utils.stripe_config import stripe_config
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
                    await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
                except stripe.error.APIConnectionError as e:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(delay)
                except stripe.error.StripeError as e:
                    # Don't retry on other Stripe errors
                    raise
            return None
        return wrapper
    return decorator

class StripeService:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.config = stripe_config
        self._webhook_event_cache = {}  # Simple in-memory cache for webhook idempotency
    
    @retry_on_stripe_error()
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
                "auth_token": auth_token[:50] if auth_token else "",  # Truncate token
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
                "allow_promotion_codes": True,  # Allow discount codes
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
    
    async def get_subscription_status(self, user_id: str) -> SubscriptionStatusResponse:
        """Get user's current subscription status with cache invalidation."""
        try:
            # Get from database
            user_response = self.supabase.table("users_metadata").select(
                "stripe_customer_id, subscription_status, subscription_plan, "
                "stripe_subscription_id, subscription_current_period_end, "
                "subscription_cancel_at_period_end, subscription_created_at, "
                "subscription_trial_end, last_payment_date"
            ).eq("user_id", user_id).single().execute()
            
            if not user_response.data:
                return SubscriptionStatusResponse(
                    isActive=False,
                    planId=None,
                    currentPeriodEnd=None,
                    cancelAtPeriodEnd=False,
                    stripeCustomerId=None,
                    stripeSubscriptionId=None
                )
            
            user_data = user_response.data
            stripe_subscription_id = user_data["stripe_subscription_id"]
            
            # Verify with Stripe if subscription exists
            if stripe_subscription_id:
                try:
                    subscription = stripe.Subscription.retrieve(
                        stripe_subscription_id,
                        expand=['latest_invoice', 'default_payment_method']
                    )
                    
                    # Check if local status differs from Stripe
                    if user_data["subscription_status"] != subscription.status:
                        logger.info(f"Subscription status mismatch for user {user_id}: "
                                  f"local={user_data['subscription_status']}, "
                                  f"stripe={subscription.status}")
                        await self._update_subscription_status(user_id, subscription)
                        
                        # Update local data
                        user_data["subscription_status"] = subscription.status
                        user_data["subscription_cancel_at_period_end"] = subscription.cancel_at_period_end
                        user_data["subscription_current_period_end"] = datetime.fromtimestamp(
                            subscription.current_period_end
                        ).isoformat()
                    
                    is_active = subscription.status in ['active', 'trialing']
                    
                    return SubscriptionStatusResponse(
                        isActive=is_active,
                        planId=user_data["subscription_plan"],
                        currentPeriodEnd=user_data["subscription_current_period_end"],
                        cancelAtPeriodEnd=user_data["subscription_cancel_at_period_end"],
                        stripeCustomerId=user_data["stripe_customer_id"],
                        stripeSubscriptionId=stripe_subscription_id
                    )
                    
                except stripe.error.StripeError as e:
                    logger.warning(f"Failed to retrieve subscription from Stripe: {str(e)}")
            
            # Return local status
            return SubscriptionStatusResponse(
                isActive=user_data["subscription_status"] == "active",
                planId=user_data["subscription_plan"],
                currentPeriodEnd=user_data["subscription_current_period_end"],
                cancelAtPeriodEnd=user_data["subscription_cancel_at_period_end"],
                stripeCustomerId=user_data["stripe_customer_id"],
                stripeSubscriptionId=stripe_subscription_id
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
    
    async def handle_webhook_event(self, event: Dict[str, Any]) -> bool:
        """Enhanced webhook handler with idempotency and better error handling."""
        event_id = event.get("id")
        event_type = event.get("type")
        event_data = event.get("data", {})
        
        print("==================================\n")
        print(event_id, event_type, event_data)
        print("==================================\n")
        
        # Check if we've already processed this event
        if event_id in self._webhook_event_cache:
            logger.info(f"Skipping already processed event {event_id}")
            return True
        
        # Check database for existing event
        existing_event = self.supabase.table("stripe_webhook_events").select(
            "id, processed"
        ).eq("stripe_event_id", event_id).maybe_single().execute()
        
        print("==================================\n")
        print(existing_event)
        print("==================================\n")
        
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
    
    async def _handle_trial_will_end(self, event_id: str, subscription: Dict[str, Any]) -> bool:
        """Handle trial ending soon notification."""
        user_id = subscription.get("metadata", {}).get("user_id")
        if not user_id:
            logger.warning(f"No user_id in trial_will_end event {event_id}")
            return False
        
        # You could send a notification to the user here
        logger.info(f"Trial will end soon for user {user_id}")
        
        # Update trial end date
        trial_end = subscription.get("trial_end")
        if trial_end:
            self.supabase.table("users_metadata").update({
                "subscription_trial_end": datetime.fromtimestamp(trial_end).isoformat()
            }).eq("user_id", user_id).execute()
        
        return True
    
    async def _handle_upcoming_invoice(self, event_id: str, invoice: Dict[str, Any]) -> bool:
        """Handle upcoming invoice notification."""
        subscription_id = invoice.get("subscription")
        if not subscription_id:
            return True
        
        # Get subscription to find user
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            user_id = subscription.metadata.get("user_id")
            
            if user_id:
                # You could send a notification about upcoming payment
                logger.info(f"Upcoming invoice for user {user_id}")
                
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve subscription for upcoming invoice: {str(e)}")
            return False
            
        return True
    
    async def _handle_customer_updated(self, event_id: str, customer: Dict[str, Any]) -> bool:
        """Handle customer information updates."""
        customer_id = customer.get("id")
        if not customer_id:
            return False
        
        # Update customer info in database
        user_response = self.supabase.table("users_metadata").select(
            "user_id"
        ).eq("stripe_customer_id", customer_id).single().execute()
        
        if user_response.data:
            update_data = {}
            if customer.get("email"):
                update_data["email"] = customer["email"]
            if customer.get("name"):
                update_data["name"] = customer["name"]
            
            if update_data:
                self.supabase.table("users_metadata").update(update_data).eq(
                    "user_id", user_response.data["user_id"]
                ).execute()
        
        return True
    
    async def _handle_payment_method_attached(self, event_id: str, payment_method: Dict[str, Any]) -> bool:
        """Handle payment method attachment."""
        customer_id = payment_method.get("customer")
        if not customer_id:
            return True
        
        # Update default payment method
        user_response = self.supabase.table("users_metadata").select(
            "user_id"
        ).eq("stripe_customer_id", customer_id).single().execute()
        
        if user_response.data:
            self.supabase.table("users_metadata").update({
                "payment_method_id": payment_method.get("id")
            }).eq("user_id", user_response.data["user_id"]).execute()
        
        return True
    
    def _get_plan_id_from_price(self, price_id: str) -> Optional[str]:
        """Get plan ID from price ID."""
        if price_id == self.config.monthly_price_id:
            return "monthly"
        elif price_id == self.config.yearly_price_id:
            return "yearly"
        return None
    
    async def _record_payment_history(self, user_id: str, invoice: Dict[str, Any]) -> None:
        """Record payment in payment history table."""
        try:
            self.supabase.table("payment_history").insert({
                "user_id": user_id,
                "stripe_payment_intent_id": invoice.get("payment_intent"),
                "stripe_invoice_id": invoice.get("id"),
                "amount": invoice.get("amount_paid", 0),
                "currency": invoice.get("currency", "eur"),
                "status": invoice.get("status"),
                "payment_date": datetime.fromtimestamp(invoice.get("status_transitions", {}).get("paid_at") or invoice.get("created")).isoformat(),
                "subscription_period_start": datetime.fromtimestamp(invoice.get("period_start")).isoformat() if invoice.get("period_start") else None,
                "subscription_period_end": datetime.fromtimestamp(invoice.get("period_end")).isoformat() if invoice.get("period_end") else None,
                "metadata": {
                    "invoice_number": invoice.get("number"),
                    "hosted_invoice_url": invoice.get("hosted_invoice_url"),
                    "invoice_pdf": invoice.get("invoice_pdf")
                }
            }).execute()
        except Exception as e:
            logger.error(f"Failed to record payment history: {str(e)}")
    
    # Enhanced payment success handler
    async def _handle_payment_succeeded(self, event_id: str, invoice: Dict[str, Any]) -> bool:
        """Handle successful payment with payment history recording."""
        subscription_id = invoice.get("subscription")
        if subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user_id = subscription.metadata.get("user_id")
                if user_id:
                    await self._update_subscription_status(user_id, subscription, event_id)
                    await self._record_payment_history(user_id, invoice)
                    
                    # Update last payment date
                    self.supabase.table("users_metadata").update({
                        "last_payment_date": datetime.now(timezone.utc).isoformat()
                    }).eq("user_id", user_id).execute()
                    
                return True
            except stripe.error.StripeError as e:
                logger.error(f"Failed to retrieve subscription {subscription_id}: {str(e)}")
                return False
        return True
    
  
    async def cancel_subscription(self, user_id: str) -> bool:
        """Cancel user's subscription."""
        try:
            # Get user's subscription ID
            user_response = self.supabase.table("users_metadata").select(
                "stripe_subscription_id"
            ).eq("user_id", user_id).single().execute()
            
            if not user_response.data or not user_response.data["stripe_subscription_id"]:
                logger.warning(f"No subscription found for user {user_id}")
                return False
            
            subscription_id = user_response.data["stripe_subscription_id"]
            
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
    
    async def _get_or_create_customer(self, user_id: str, user_email: str) -> stripe.Customer:
        """Get existing Stripe customer or create a new one."""
        # Check if customer exists in database
        user_response = self.supabase.table("users_metadata").select(
            "stripe_customer_id, name"
        ).eq("user_id", user_id).single().execute()
        
        customer_id = user_response.data["stripe_customer_id"]
        
        if customer_id:
            try:
                return stripe.Customer.retrieve(customer_id)
            except stripe.error.StripeError:
                logger.warning(f"Stripe customer {customer_id} not found, creating new one")
        
        # Create new customer
        customer_name = user_response.data["name"]
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

    async def _log_subscription_change(
        self,
        user_id: str,
        old_status: Optional[str],
        new_status: Optional[str],
        old_plan: Optional[str],
        new_plan: Optional[str],
        stripe_event_id: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert a record into subscription_audit_log."""
        try:
            self.supabase.table("subscription_audit_log").insert({
                "user_id": user_id,
                "old_status": old_status,
                "new_status": new_status,
                "old_plan": old_plan,
                "new_plan": new_plan,
                "stripe_event_id": stripe_event_id,
                "changed_by": "webhook",
                "metadata": metadata or {},
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log subscription change for user {user_id}: {e}")

    async def _update_subscription_status(
        self,
        user_id: str,
        subscription: stripe.Subscription,
        stripe_event_id: Optional[str] = None,
    ):
        """Update user's subscription status in the database."""
        try:
            # Ensure required subscription fields are present. Some webhook
            # payloads omit certain attributes, so fetch the full subscription
            # object from Stripe when needed.
            if not getattr(subscription, "current_period_end", None):
                try:
                    subscription = stripe.Subscription.retrieve(subscription.id)
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        f"Failed to retrieve subscription {subscription.id}: {e}"
                    )
            print("==================================\n")
            print(subscription)
            print("==================================\n")
            current = self.supabase.table("users_metadata").select(
                "subscription_status, subscription_plan"
            ).eq("user_id", user_id).single().execute()
            if current.data:
                old_status = current.data["subscription_status"]
                old_plan = current.data["subscription_plan"]
            else:
                old_status = None
                old_plan = None

            # Determine the plan ID. Prefer the value stored in the
            # subscription metadata (written during checkout creation). This
            # fallback to price ID comparison maintains backwards compatibility
            # with older sessions where the metadata may not be present.
            product_id = subscription.get('items').get('data')[0].get('plan').get('product')
            if product_id == self.config.plus_product_id:
                subscription_plan = "plus"
            else:
                subscription_plan = None
            
            # Update database
            period_end = getattr(subscription, "current_period_end", None)
            update_data = {
                "stripe_customer_id": subscription.customer,
                "stripe_subscription_id": subscription.id,
                "subscription_status": subscription.status,
                "subscription_plan": subscription_plan,
                "subscription_current_period_end": datetime.fromtimestamp(period_end).isoformat() if period_end else None,
                "subscription_cancel_at_period_end": subscription.cancel_at_period_end,
            }
            self.supabase.table("users_metadata").update(update_data).eq(
                "user_id", user_id
            ).execute()

            logger.info(
                f"Updated subscription status for user {user_id}: {subscription.status}"
            )

            if old_status != update_data["subscription_status"] or old_plan != update_data["subscription_plan"]:
                await self._log_subscription_change(
                    user_id,
                    old_status,
                    update_data["subscription_status"],
                    old_plan,
                    update_data["subscription_plan"],
                    stripe_event_id,
                    {"subscription_id": subscription.id},
                )

        except Exception as e:
            logger.error(f"Failed to update subscription status for user {user_id}: {str(e)}")
    

    
    async def _handle_subscription_created(self, event_id: str, subscription: Dict[str, Any]):
        """Handle subscription created event."""

        user_id = subscription["metadata"].get("user_id")
        if user_id:
            # Convert subscription dict to Stripe object for consistency
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
            current = self.supabase.table("users_metadata").select(
                "subscription_status, subscription_plan"
            ).eq("user_id", user_id).single().execute()
            old_status = current.data["subscription_status"]
            old_plan = current.data["subscription_plan"]

            self.supabase.table("users_metadata").update({
                "subscription_status": "cancelled",
                "subscription_plan": None,
                "subscription_cancel_at_period_end": False
            }).eq("user_id", user_id).execute()

            await self._log_subscription_change(
                user_id,
                old_status,
                "cancelled",
                old_plan,
                None,
                event_id,
                {"subscription_id": subscription.get("id")},
            )

            logger.info(f"Marked subscription as cancelled for user {user_id}")
    
    
    async def _handle_payment_failed(self, event_id: str, invoice: Dict[str, Any]):
        """Handle failed payment."""
        # Payment failed - mark subscription as past due
        subscription_id = invoice.get("subscription")
        if subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user_id = subscription.metadata.get("user_id")
                if user_id:
                    await self._update_subscription_status(user_id, subscription, event_id)
            except stripe.error.StripeError as e:
                logger.error(f"Failed to retrieve subscription {subscription_id}: {str(e)}")
                
                
    async def _process_webhook_event(self, event_id: str, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Process different types of webhook events."""
        handlers = {
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "customer.subscription.trial_will_end": self._handle_trial_will_end,
            "invoice.payment_succeeded": self._handle_payment_succeeded,
            "invoice.payment_failed": self._handle_payment_failed,
            "invoice.upcoming": self._handle_upcoming_invoice,
            "customer.updated": self._handle_customer_updated,
            "payment_method.attached": self._handle_payment_method_attached,
        }
        
        handler = handlers.get(event_type)
        if handler:
            return await handler(event_id, event_data.get("object", {}))
        else:
            logger.info(f"No handler for event type: {event_type}")
            return True  # Consider unhandled events as successful