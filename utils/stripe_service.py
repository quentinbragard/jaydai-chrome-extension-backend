# utils/stripe_service.py
import stripe
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from supabase import Client
from utils.stripe_config import stripe_config
from models.stripe import SubscriptionStatusResponse
import os

logger = logging.getLogger(__name__)

class StripeService:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.config = stripe_config
    
    async def create_checkout_session(
        self, 
        price_id: str, 
        user_id: str, 
        auth_token: str,
        user_email: str, 
        success_url: str, 
        cancel_url: str
    ) -> Dict[str, Any]:
        """Create a Stripe checkout session."""
        try:
            # Check if customer already exists
            customer = await self._get_or_create_customer(user_id, user_email)
            
            # Determine if the environment is production
            is_prod = os.getenv("ENVIRONMENT") == "prod"
            success_url_suffix = '&session-id={CHECKOUT_SESSION_ID}'
            if auth_token:
                success_url_suffix += f'&auth_token={auth_token}'
            if not is_prod:
                success_url_suffix += '&dev=true'
            
            # Create checkout session
            # Determine plan identifier based on the provided price ID. This
            # information will be stored on both the checkout session and the
            # resulting subscription so that webhook processing can reliably
            # update the user's plan even if price IDs change.
            plan_id = None
            if price_id == self.config.monthly_price_id:
                plan_id = "monthly"
            elif price_id == self.config.yearly_price_id:
                plan_id = "yearly"

            metadata = {"user_id": user_id}
            if plan_id:
                metadata["plan_id"] = plan_id

            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url + success_url_suffix,
                cancel_url=cancel_url,
                metadata=metadata,
                subscription_data={'metadata': metadata}
            )
            
            logger.info(
                f"Created checkout session {session.id} for user {user_id}; "
                f"Success URL: {success_url + success_url_suffix}"
            )
            
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
        """Get user's current subscription status."""
        try:
            # Get user's Stripe customer ID from database
            user_response = self.supabase.table("users_metadata").select(
                "stripe_customer_id, subscription_status, subscription_plan, "
                "stripe_subscription_id, subscription_current_period_end, "
                "subscription_cancel_at_period_end"
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
            
            # If we have a subscription ID, verify with Stripe
            if stripe_subscription_id:
                try:
                    subscription = stripe.Subscription.retrieve(stripe_subscription_id)
                    
                    # Update local status if it's different from Stripe
                    stripe_status = subscription.status
                    is_active = stripe_status in ['active', 'trialing']
                    
                    # Update database if status has changed
                    if user_data["subscription_status"] != stripe_status:
                        await self._update_subscription_status(user_id, subscription)
                    
                    return SubscriptionStatusResponse(
                        isActive=is_active,
                        planId=user_data["subscription_plan"],
                        currentPeriodEnd=datetime.fromtimestamp(
                            subscription.current_period_end
                        ).isoformat() if subscription.current_period_end else None,
                        cancelAtPeriodEnd=subscription.cancel_at_period_end or False,
                        stripeCustomerId=user_data["stripe_customer_id"],
                        stripeSubscriptionId=stripe_subscription_id
                    )
                    
                except stripe.error.StripeError as e:
                    logger.warning(f"Failed to retrieve subscription from Stripe: {str(e)}")
            
            # Return local status if Stripe lookup fails
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
            plan_id = subscription.metadata.get("plan_id")

            price_id = None
            if not plan_id:
                price_id = subscription.items.data[0].price.id
                if price_id == self.config.monthly_price_id:
                    plan_id = "monthly"
                elif price_id == self.config.yearly_price_id:
                    plan_id = "yearly"
            
            # Update database
            update_data = {
                "stripe_customer_id": subscription.customer,
                "stripe_subscription_id": subscription.id,
                "subscription_status": subscription.status,
                "subscription_plan": plan_id,
                "subscription_current_period_end": datetime.fromtimestamp(
                    subscription.current_period_end
                ).isoformat(),
                "subscription_cancel_at_period_end": subscription.cancel_at_period_end
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
    
    async def handle_webhook_event(self, event: Dict[str, Any]) -> bool:
        """Handle Stripe webhook events and persist them."""
        event_id = event.get("id")
        event_type = event.get("type")
        event_data = event.get("data", {})

        record_id = await self._record_webhook_event(event_id, event_type, event_data)
        success = True
        try:
            if event_type == "customer.subscription.created":
                await self._handle_subscription_created(event_id, event_data["object"])
            elif event_type == "customer.subscription.updated":
                await self._handle_subscription_updated(event_id, event_data["object"])
            elif event_type == "customer.subscription.deleted":
                await self._handle_subscription_deleted(event_id, event_data["object"])
            elif event_type == "invoice.payment_succeeded":
                await self._handle_payment_succeeded(event_id, event_data["object"])
            elif event_type == "invoice.payment_failed":
                await self._handle_payment_failed(event_id, event_data["object"])
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")

        except Exception as e:
            logger.error(f"Error handling webhook event {event_type}: {str(e)}")
            success = False

        try:
            if record_id:
                self.supabase.table("stripe_webhook_events").update({
                    "processed": success,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", record_id).execute()
        except Exception as e:
            logger.error(f"Failed to update webhook event record {event_id}: {e}")

        return success
    
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
    
    async def _handle_payment_succeeded(self, event_id: str, invoice: Dict[str, Any]):
        """Handle successful payment."""
        # Payment succeeded - subscription should be active
        subscription_id = invoice.get("subscription")
        if subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user_id = subscription.metadata.get("user_id")
                if user_id:
                    await self._update_subscription_status(user_id, subscription, event_id)
            except stripe.error.StripeError as e:
                logger.error(f"Failed to retrieve subscription {subscription_id}: {str(e)}")
    
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