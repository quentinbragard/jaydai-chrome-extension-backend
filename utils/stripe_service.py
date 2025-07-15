# utils/stripe_service.py - COMPREHENSIVE FIX
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
        
        # Validate supabase client
        if not hasattr(supabase_client, 'table'):
            raise ValueError("Invalid Supabase client provided")
    
    def _validate_supabase_client(self):
        """Validate that the Supabase client is properly initialized."""
        try:
            # Test the client with a simple operation
            result = self.supabase.table("users_metadata").select("user_id").limit(1).execute()
            return hasattr(result, 'data')
        except Exception as e:
            logger.error(f"Supabase client validation failed: {str(e)}")
            return False
    
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
                metadata={
                    'user_id': user_id
                },
                subscription_data={
                    'metadata': {
                        'user_id': user_id
                    }
                }
            )
            
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
        """Get user's current subscription status."""
        try:
            # Validate Supabase client
            if not self._validate_supabase_client():
                logger.error("Supabase client validation failed")
                return SubscriptionStatusResponse(
                    isActive=False,
                    planId=None,
                    currentPeriodEnd=None,
                    cancelAtPeriodEnd=False,
                    stripeCustomerId=None,
                    stripeSubscriptionId=None
                )
            
            # Get user's Stripe customer ID from database
            try:
                user_response = self.supabase.table("users_metadata").select(
                    "stripe_customer_id, subscription_status, subscription_plan, "
                    "stripe_subscription_id, subscription_current_period_end, "
                    "subscription_cancel_at_period_end"
                ).eq("user_id", user_id).maybe_single().execute()
                
                logger.info(f"User response type: {type(user_response)}")
                logger.info(f"User response has data: {hasattr(user_response, 'data')}")
                
                if not hasattr(user_response, 'data') or not user_response.data:
                    logger.warning(f"No user data found for user_id: {user_id}")
                    return SubscriptionStatusResponse(
                        isActive=False,
                        planId=None,
                        currentPeriodEnd=None,
                        cancelAtPeriodEnd=False,
                        stripeCustomerId=None,
                        stripeSubscriptionId=None
                    )
                
                user_data = user_response.data
                
            except Exception as e:
                logger.error(f"Error querying user data: {str(e)}")
                return SubscriptionStatusResponse(
                    isActive=False,
                    planId=None,
                    currentPeriodEnd=None,
                    cancelAtPeriodEnd=False,
                    stripeCustomerId=None,
                    stripeSubscriptionId=None
                )
            
            stripe_subscription_id = user_data.get("stripe_subscription_id")
            
            # If we have a subscription ID, verify with Stripe
            if stripe_subscription_id:
                try:
                    subscription = stripe.Subscription.retrieve(stripe_subscription_id)
                    
                    # Update local status if it's different from Stripe
                    stripe_status = subscription.status
                    is_active = stripe_status in ['active', 'trialing']
                    
                    # Update database if status has changed
                    if user_data.get("subscription_status") != stripe_status:
                        await self._update_subscription_status(user_id, subscription)
                    
                    return SubscriptionStatusResponse(
                        isActive=is_active,
                        planId=user_data.get("subscription_plan"),
                        currentPeriodEnd=datetime.fromtimestamp(
                            subscription.current_period_end
                        ).isoformat() if subscription.current_period_end else None,
                        cancelAtPeriodEnd=subscription.cancel_at_period_end or False,
                        stripeCustomerId=user_data.get("stripe_customer_id"),
                        stripeSubscriptionId=stripe_subscription_id
                    )
                    
                except stripe.error.StripeError as e:
                    logger.warning(f"Failed to retrieve subscription from Stripe: {str(e)}")
            
            # Return local status if Stripe lookup fails
            return SubscriptionStatusResponse(
                isActive=user_data.get("subscription_status") == "active",
                planId=user_data.get("subscription_plan"),
                currentPeriodEnd=user_data.get("subscription_current_period_end"),
                cancelAtPeriodEnd=user_data.get("subscription_cancel_at_period_end", False),
                stripeCustomerId=user_data.get("stripe_customer_id"),
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
            ).eq("user_id", user_id).maybe_single().execute()
            
            if not hasattr(user_response, 'data') or not user_response.data or not user_response.data.get("stripe_subscription_id"):
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
            ).eq("user_id", user_id).maybe_single().execute()
            
            if not hasattr(user_response, 'data') or not user_response.data or not user_response.data.get("stripe_customer_id"):
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
        try:
            # Check if customer exists in database
            user_response = self.supabase.table("users_metadata").select(
                "stripe_customer_id, name"
            ).eq("user_id", user_id).maybe_single().execute()
            
            customer_id = None
            customer_name = None
            
            if hasattr(user_response, 'data') and user_response.data:
                customer_id = user_response.data.get("stripe_customer_id")
                customer_name = user_response.data.get("name")
            
            if customer_id:
                try:
                    return stripe.Customer.retrieve(customer_id)
                except stripe.error.StripeError:
                    logger.warning(f"Stripe customer {customer_id} not found, creating new one")
            
            # Create new customer
            customer = stripe.Customer.create(
                email=user_email,
                name=customer_name,
                metadata={
                    'user_id': user_id
                }
            )
            
            # Update database with customer ID
            try:
                self.supabase.table("users_metadata").upsert({
                    "user_id": user_id,
                    "stripe_customer_id": customer.id
                }, on_conflict="user_id").execute()
            except Exception as e:
                logger.error(f"Failed to update customer ID in database: {str(e)}")
            
            logger.info(f"Created new Stripe customer {customer.id} for user {user_id}")
            return customer
            
        except Exception as e:
            logger.error(f"Error in _get_or_create_customer: {str(e)}")
            raise
    
    async def _record_webhook_event(self, event_id: str, event_type: str, event_data: Dict[str, Any]) -> Optional[str]:
        """Persist webhook event payload in the database."""
        try:
            if not self._validate_supabase_client():
                logger.error("Cannot record webhook event - Supabase client invalid")
                return None
                
            response = self.supabase.table("stripe_webhook_events").insert({
                "stripe_event_id": event_id,
                "event_type": event_type,
                "event_data": event_data,
            }).execute()
            
            if hasattr(response, 'data') and response.data:
                return response.data[0]["id"]
                
        except Exception as e:
            logger.error(f"Failed to record webhook event {event_id}: {str(e)}")
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
            if not self._validate_supabase_client():
                logger.error("Cannot log subscription change - Supabase client invalid")
                return
                
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
            logger.error(f"Failed to log subscription change for user {user_id}: {str(e)}")

    async def _update_subscription_status(
        self,
        user_id: str,
        subscription: stripe.Subscription,
        stripe_event_id: Optional[str] = None,
    ):
        """Update user's subscription status in the database."""
        try:
            logger.info(f"Updating subscription status for user: {user_id}")
            
            # Validate Supabase client first
            if not self._validate_supabase_client():
                logger.error("Supabase client validation failed in _update_subscription_status")
                raise Exception("Supabase client is not properly initialized")
            
            # Get current subscription status with robust error handling
            old_status = None
            old_plan = None
            
            try:
                current_response = self.supabase.table("users_metadata").select(
                    "subscription_status, subscription_plan"
                ).eq("user_id", user_id).maybe_single().execute()
                
                logger.info(f"Current response type: {type(current_response)}")
                logger.info(f"Current response has data attr: {hasattr(current_response, 'data')}")
                
                if hasattr(current_response, 'data') and current_response.data:
                    old_status = current_response.data.get("subscription_status")
                    old_plan = current_response.data.get("subscription_plan")
                    logger.info(f"Found existing status: {old_status}, plan: {old_plan}")
                else:
                    logger.info("No existing subscription data found")
                    
            except Exception as e:
                logger.error(f"Error fetching current subscription status: {str(e)}")
                # Continue with None values
            
            # Determine plan type from price ID
            if not subscription.items or not subscription.items.data:
                logger.error("No subscription items found")
                raise Exception("Invalid subscription data - no items")
                
            price_id = subscription.items.data[0].price.id
            logger.info(f"Processing subscription with price_id: {price_id}")
            
            plan_id = None
            if price_id == self.config.monthly_price_id:
                plan_id = "monthly"
            elif price_id == self.config.yearly_price_id:
                plan_id = "yearly"
            else:
                logger.warning(f"Unknown price_id: {price_id}")
            
            # Prepare update data
            update_data = {
                "user_id": user_id,  # Include user_id for upsert
                "stripe_customer_id": subscription.customer,
                "stripe_subscription_id": subscription.id,
                "subscription_status": subscription.status,
                "subscription_plan": plan_id,
                "subscription_current_period_end": datetime.fromtimestamp(
                    subscription.current_period_end
                ).isoformat(),
                "subscription_cancel_at_period_end": subscription.cancel_at_period_end or False
            }
            
            logger.info(f"Updating user {user_id} with data: {update_data}")
            
            # Update database with upsert
            try:
                update_response = self.supabase.table("users_metadata").upsert(
                    update_data,
                    on_conflict="user_id"
                ).execute()
                
                logger.info(f"Update response type: {type(update_response)}")
                logger.info(f"Update response has data: {hasattr(update_response, 'data')}")
                
                if hasattr(update_response, 'data'):
                    logger.info(f"Update successful for user {user_id}")
                else:
                    logger.warning(f"Update response format unexpected: {update_response}")
                    
            except Exception as e:
                logger.error(f"Error updating subscription status: {str(e)}")
                raise e

            logger.info(f"Successfully updated subscription status for user {user_id}: {subscription.status}")

            # Log subscription change if status or plan changed
            if old_status != update_data["subscription_status"] or old_plan != update_data["subscription_plan"]:
                try:
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
                    logger.error(f"Failed to log subscription change: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to update subscription status for user {user_id}: {str(e)}")
            raise e
    
    async def handle_webhook_event(self, event: Dict[str, Any]) -> bool:
        """Handle Stripe webhook events and persist them."""
        event_id = event.get("id")
        event_type = event.get("type")
        event_data = event.get("data", {})

        logger.info(f"Handling webhook event: {event_type} with ID: {event_id}")

        # Validate Supabase client
        if not self._validate_supabase_client():
            logger.error("Supabase client validation failed in handle_webhook_event")
            return False

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

        # Update webhook event record
        try:
            if record_id:
                self.supabase.table("stripe_webhook_events").update({
                    "processed": success,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", record_id).execute()
        except Exception as e:
            logger.error(f"Failed to update webhook event record {event_id}: {str(e)}")

        return success
    
    async def _handle_subscription_created(self, event_id: str, subscription_data: Dict[str, Any]):
        """Handle subscription created event."""
        try:
            logger.info(f"Handling subscription created event: {event_id}")
            
            user_id = subscription_data.get("metadata", {}).get("user_id")
            logger.info(f"User ID from subscription metadata: {user_id}")
            
            if not user_id:
                logger.error("No user_id found in subscription metadata")
                return
            
            # Convert subscription dict to Stripe object for consistency
            try:
                stripe_subscription = stripe.Subscription.construct_from(
                    subscription_data, 
                    stripe.api_key
                )
                logger.info(f"Created Stripe subscription object: {stripe_subscription.id}")
                
                await self._update_subscription_status(user_id, stripe_subscription, event_id)
                logger.info(f"Successfully processed subscription created for user {user_id}")
                
            except Exception as e:
                logger.error(f"Error constructing Stripe subscription object: {str(e)}")
                raise e
                
        except Exception as e:
            logger.error(f"Error in _handle_subscription_created: {str(e)}")
            raise e
    
    async def _handle_subscription_updated(self, event_id: str, subscription_data: Dict[str, Any]):
        """Handle subscription updated event."""
        try:
            logger.info(f"Handling subscription updated event: {event_id}")
            
            user_id = subscription_data.get("metadata", {}).get("user_id")
            if not user_id:
                logger.error("No user_id found in subscription metadata")
                return
                
            stripe_subscription = stripe.Subscription.construct_from(
                subscription_data, 
                stripe.api_key
            )
            await self._update_subscription_status(user_id, stripe_subscription, event_id)
            logger.info(f"Successfully processed subscription updated for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in _handle_subscription_updated: {str(e)}")
            raise e
    
    async def _handle_subscription_deleted(self, event_id: str, subscription_data: Dict[str, Any]):
        """Handle subscription deleted event."""
        try:
            logger.info(f"Handling subscription deleted event: {event_id}")
            
            user_id = subscription_data.get("metadata", {}).get("user_id")
            if not user_id:
                logger.error("No user_id found in subscription metadata")
                return
            
            # Get current status for logging
            old_status = None
            old_plan = None
            
            try:
                current_response = self.supabase.table("users_metadata").select(
                    "subscription_status, subscription_plan"
                ).eq("user_id", user_id).maybe_single().execute()
                
                if hasattr(current_response, 'data') and current_response.data:
                    old_status = current_response.data.get("subscription_status")
                    old_plan = current_response.data.get("subscription_plan")
            except Exception as e:
                logger.error(f"Error fetching current status: {str(e)}")

            # Update to cancelled status
            self.supabase.table("users_metadata").upsert({
                "user_id": user_id,
                "subscription_status": "cancelled",
                "subscription_plan": None,
                "subscription_cancel_at_period_end": False
            }, on_conflict="user_id").execute()

            # Log the change
            await self._log_subscription_change(
                user_id,
                old_status,
                "cancelled",
                old_plan,
                None,
                event_id,
                {"subscription_id": subscription_data.get("id")},
            )

            logger.info(f"Successfully processed subscription deletion for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in _handle_subscription_deleted: {str(e)}")
            raise e
    
    async def _handle_payment_succeeded(self, event_id: str, invoice_data: Dict[str, Any]):
        """Handle successful payment."""
        try:
            logger.info(f"Handling payment succeeded event: {event_id}")
            
            subscription_id = invoice_data.get("subscription")
            if not subscription_id:
                logger.warning("No subscription ID found in payment succeeded event")
                return
                
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user_id = subscription.metadata.get("user_id")
                
                if user_id:
                    await self._update_subscription_status(user_id, subscription, event_id)
                    logger.info(f"Successfully processed payment succeeded for user {user_id}")
                else:
                    logger.warning(f"No user_id found in subscription {subscription_id}")
                    
            except stripe.error.StripeError as e:
                logger.error(f"Failed to retrieve subscription {subscription_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in _handle_payment_succeeded: {str(e)}")
            raise e
    
    async def _handle_payment_failed(self, event_id: str, invoice_data: Dict[str, Any]):
        """Handle failed payment."""
        try:
            logger.info(f"Handling payment failed event: {event_id}")
            
            subscription_id = invoice_data.get("subscription")
            if not subscription_id:
                logger.warning("No subscription ID found in payment failed event")
                return
                
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user_id = subscription.metadata.get("user_id")
                
                if user_id:
                    await self._update_subscription_status(user_id, subscription, event_id)
                    logger.info(f"Successfully processed payment failed for user {user_id}")
                else:
                    logger.warning(f"No user_id found in subscription {subscription_id}")
                    
            except stripe.error.StripeError as e:
                logger.error(f"Failed to retrieve subscription {subscription_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in _handle_payment_failed: {str(e)}")
            raise e