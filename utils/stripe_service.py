# utils/stripe_service.py - Enhanced with Amplitude tracking
import logging
from typing import Dict, Any, Optional
from supabase import Client
from datetime import datetime

# Import all service modules
from services.stripe.checkout import create_checkout_session, verify_checkout_session
from services.stripe.subscriptions import (
    get_subscription_status, 
    cancel_subscription, 
    reactivate_subscription,
    update_subscription_status
)
from services.stripe.portal import create_customer_portal_session
from services.stripe.customer import ensure_stripe_customer
from services.stripe.webhooks import handle_webhook_event
from utils.amplitude import track_event, identify_user

logger = logging.getLogger(__name__)

class StripeService:
    """Enhanced Stripe service with comprehensive Amplitude tracking."""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase

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
        """Create a checkout session with Amplitude tracking."""
        
        # Track checkout session creation attempt
        track_event(user_id, "Checkout Session Requested", {
            "price_id": price_id,
            "user_email": user_email,
            "redirect_url": redirect_url,
            "has_auth_token": bool(auth_token)
        })
        
        try:
            result = await create_checkout_session(
                self.supabase,
                price_id=price_id,
                user_id=user_id,
                auth_token=auth_token,
                user_email=user_email,
                success_url=success_url,
                cancel_url=cancel_url,
                redirect_url=redirect_url,
            )
            
            if result["success"]:
                # Track successful checkout session creation
                track_event(user_id, "Checkout Session Created", {
                    "price_id": price_id,
                    "session_id": result["sessionId"],
                    "checkout_url": result["url"]
                })
                
                # Update user properties
                identify_user(user_id, {
                    "last_checkout_attempt": "successful",
                    "last_checkout_price_id": price_id
                })
            else:
                # Track failed checkout session creation
                track_event(user_id, "Checkout Session Failed", {
                    "price_id": price_id,
                    "error": result.get("error", "Unknown error"),
                    "reason": "creation_failed"
                })
                
                identify_user(user_id, {
                    "last_checkout_attempt": "failed",
                    "last_checkout_error": result.get("error", "Unknown error")
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating checkout session for user {user_id}: {str(e)}")
            
            # Track exception
            track_event(user_id, "Checkout Session Error", {
                "price_id": price_id,
                "error": str(e),
                "error_type": type(e).__name__
            })
            
            return {"success": False, "error": "An unexpected error occurred"}

    async def verify_checkout_session(self, session_id: str) -> Dict[str, Any]:
        """Verify a checkout session with Amplitude tracking."""
        try:
            result = await verify_checkout_session(self.supabase, session_id)
            
            if result["success"] and result.get("subscription"):
                subscription = result["subscription"]
                user_id = subscription.stripeCustomerId  # Assuming this contains user mapping
                
                # Note: Additional tracking is handled in webhook events
                # This is just for immediate verification tracking
                track_event(user_id, "Checkout Session Verified", {
                    "session_id": session_id,
                    "subscription_status": subscription.status,
                    "plan_name": subscription.planName
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error verifying checkout session {session_id}: {str(e)}")
            return {"success": False, "error": "Verification failed"}

    async def get_subscription_status(self, user_id: str):
        """Get subscription status with usage tracking."""
        try:
            return await get_subscription_status(self.supabase, user_id)
            
        except Exception as e:
            logger.error(f"Error getting subscription status for user {user_id}: {str(e)}")
            track_event(user_id, "Subscription Status Error", {
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

    async def cancel_subscription(self, user_id: str) -> bool:
        """Cancel subscription with Amplitude tracking."""
        try:
            # Track cancellation attempt
            track_event(user_id, "Subscription Cancellation Requested", {
                "source": "user_action"
            })
            
            success = await cancel_subscription(self.supabase, user_id)
            
            if success:
                track_event(user_id, "Subscription Cancellation Succeeded", {
                    "cancellation_method": "api_request",
                    "cancel_at_period_end": True  # Based on your implementation
                })
                
                # Update user properties
                identify_user(user_id, {
                    "subscription_cancel_requested_at": "now",
                    "cancellation_source": "user_portal"
                })
            else:
                track_event(user_id, "Subscription Cancellation Failed", {
                    "reason": "no_active_subscription_found"
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Error cancelling subscription for user {user_id}: {str(e)}")
            
            track_event(user_id, "Subscription Cancellation Error", {
                "error": str(e),
                "error_type": type(e).__name__
            })
            
            return False

    async def reactivate_subscription(self, user_id: str) -> bool:
        """Reactivate subscription with Amplitude tracking."""
        try:
            # Track reactivation attempt
            track_event(user_id, "Subscription Reactivation Requested", {
                "source": "user_action"
            })
            
            success = await reactivate_subscription(self.supabase, user_id)
            
            if success:
                track_event(user_id, "Subscription Reactivation Succeeded", {
                    "reactivation_method": "api_request"
                })
                
                # Update user properties
                identify_user(user_id, {
                    "subscription_reactivated_at": "now",
                    "is_paying_customer": True
                })
            else:
                track_event(user_id, "Subscription Reactivation Failed", {
                    "reason": "no_cancelled_subscription_found"
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Error reactivating subscription for user {user_id}: {str(e)}")
            
            track_event(user_id, "Subscription Reactivation Error", {
                "error": str(e),
                "error_type": type(e).__name__
            })
            
            return False

    async def create_customer_portal_session(self, user_id: str, return_url: str) -> Optional[str]:
        """Create customer portal session with Amplitude tracking."""
        try:
            # Track portal access attempt
            track_event(user_id, "Customer Portal Requested", {
                "return_url": return_url,
                "source": "api_request"
            })
            
            portal_url = await create_customer_portal_session(self.supabase, user_id, return_url)
            
            if portal_url:
                track_event(user_id, "Customer Portal Created", {
                    "portal_url": portal_url,
                    "return_url": return_url
                })
                
                # Update user properties
                identify_user(user_id, {
                    "last_portal_access": "now",
                    "portal_access_count": 1  # You might want to increment this
                })
            else:
                track_event(user_id, "Customer Portal Failed", {
                    "reason": "no_active_subscription_or_customer"
                })
            
            return portal_url
            
        except Exception as e:
            logger.error(f"Error creating customer portal for user {user_id}: {str(e)}")
            
            track_event(user_id, "Customer Portal Error", {
                "error": str(e),
                "error_type": type(e).__name__
            })
            
            return None

    async def handle_webhook_event(self, event: Dict[str, Any]) -> bool:
        """Handle webhook events with enhanced tracking."""
        event_type = event.get("type")
        event_id = event.get("id")
        
        # Track webhook received
        event_data = event.get("data", {})
        user_id = None
        
        # Try to extract user_id for tracking
        if obj := event_data.get("object", {}):
            user_id = obj.get("metadata", {}).get("user_id")
            if not user_id and event_type.startswith("invoice."):
                # For invoice events, try to get user_id from subscription
                if subscription_id := obj.get("subscription"):
                    try:
                        import stripe
                        subscription = stripe.Subscription.retrieve(subscription_id)
                        user_id = subscription.metadata.get("user_id")
                    except:
                        pass
            
        
        try:
            success = await handle_webhook_event(self.supabase, event)
            return success
            
        except Exception as e:
            logger.error(f"Error handling webhook event {event_id}: {str(e)}")
            
            if user_id:
                track_event(user_id, "Stripe Webhook Error", {
                    "event_type": event_type,
                    "event_id": event_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
            
            return False

    async def ensure_customer(self, user_id: str, user_email: str):
        """Ensure Stripe customer exists with tracking."""
        try:
            track_event(user_id, "Stripe Customer Ensure Requested", {
                "user_email": user_email
            })
            
            customer = await ensure_stripe_customer(self.supabase, user_id, user_email)
            
            track_event(user_id, "Stripe Customer Ensured", {
                "customer_id": customer.id,
                "user_email": user_email,
                "was_existing": bool(customer.created < (datetime.utcnow().timestamp() - 60))  # Created more than 1 min ago
            })
            
            return customer
            
        except Exception as e:
            logger.error(f"Error ensuring customer for user {user_id}: {str(e)}")
            
            track_event(user_id, "Stripe Customer Ensure Error", {
                "error": str(e),
                "error_type": type(e).__name__,
                "user_email": user_email
            })
            
            raise

    # Utility methods for analytics
    async def track_subscription_metrics(self, user_id: str):
        """Track comprehensive subscription metrics for a user."""
        try:
            subscription_status = await self.get_subscription_status(user_id)
            
            # Get user metadata for additional context
            user_data = self.supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
            
            metrics = {
                "subscription_status": subscription_status.status,
                "plan_name": subscription_status.planName,
                "is_trial": bool(subscription_status.trialEnd),
                "cancel_at_period_end": subscription_status.cancelAtPeriodEnd,
                "has_payment_method": bool(subscription_status.stripeCustomerId),
            }
            
            if subscription_status.currentPeriodEnd:
                current_time = datetime.utcnow().timestamp()
                period_end = datetime.fromisoformat(subscription_status.currentPeriodEnd.replace('Z', '+00:00')).timestamp()
                metrics["days_until_renewal"] = max(0, (period_end - current_time) / 86400)
            
            if subscription_status.trialEnd:
                trial_end = datetime.fromisoformat(subscription_status.trialEnd.replace('Z', '+00:00')).timestamp()
                current_time = datetime.utcnow().timestamp()
                metrics["days_until_trial_end"] = max(0, (trial_end - current_time) / 86400)
                metrics["is_trial_active"] = trial_end > current_time
            
            # Update user properties with comprehensive subscription data
            identify_user(user_id, {
                **metrics,
                "last_subscription_check": datetime.utcnow().isoformat(),
                "stripe_customer_id": subscription_status.stripeCustomerId,
                "stripe_subscription_id": subscription_status.stripeSubscriptionId
            })
                        
            return metrics
            
        except Exception as e:
            logger.error(f"Error tracking subscription metrics for user {user_id}: {str(e)}")            
            return None