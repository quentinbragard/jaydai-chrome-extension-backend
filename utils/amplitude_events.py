# utils/amplitude_events.py - Stripe event tracking functions
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from utils.amplitude import amplitude_service, identify_user, track_revenue

logger = logging.getLogger(__name__)

def track_inactive_event(user_id: str, event_name: str, properties: Dict[str, Any]):
    """Track an inactive event (will appear gray in Amplitude timeline)."""
    if not user_id:
        return
        
    # Add standard properties for all Stripe events
    enhanced_properties = {
        **properties,
        "event_category": "stripe_payment",
        "is_active_event": False,  # This makes the event inactive/gray
        "timestamp": datetime.utcnow().isoformat(),
        "source": "stripe_webhook"
    }
    
    amplitude_service.track_event(user_id, event_name, enhanced_properties)

def track_payment_succeeded(user_id: str, amount: float, currency: str = "USD", 
                          subscription_id: Optional[str] = None, 
                          plan_name: Optional[str] = None,
                          billing_reason: Optional[str] = None,
                          invoice_id: Optional[str] = None):
    """Track successful payment - inactive event."""
    track_inactive_event(
        user_id, 
        "Stripe Payment Succeeded",
        {
            "amount": amount,
            "currency": currency,
            "subscription_id": subscription_id,
            "plan_name": plan_name,
            "billing_reason": billing_reason,
            "invoice_id": invoice_id,
            "is_first_payment": billing_reason == "subscription_create"
        }
    )
    
    # Track revenue (this is important for business metrics)
    track_revenue(user_id, amount, currency, plan_name, {
        "subscription_id": subscription_id,
        "billing_reason": billing_reason,
        "invoice_id": invoice_id
    })
    
    # Update user properties
    identify_user(user_id, {
        "last_payment_date": datetime.utcnow().isoformat(),
        "last_payment_amount": amount,
        "payment_failure_count": 0,  # Reset on successful payment
        "is_paying_customer": True
    })

def track_payment_failed(user_id: str, amount: float, currency: str = "USD",
                       subscription_id: Optional[str] = None,
                       failure_reason: Optional[str] = None,
                       attempt_count: int = 1):
    """Track failed payment - inactive event."""
    track_inactive_event(
        user_id,
        "Stripe Payment Failed", 
        {
            "amount": amount,
            "currency": currency,
            "subscription_id": subscription_id,
            "failure_reason": failure_reason,
            "attempt_count": attempt_count
        }
    )
    
    # Update user properties for churn risk
    identify_user(user_id, {
        "last_payment_failure": datetime.utcnow().isoformat(),
        "payment_failure_count": attempt_count,
        "last_failure_reason": failure_reason
    })

def track_subscription_created(user_id: str, subscription_id: str, plan_name: str,
                             amount: float, currency: str = "USD",
                             is_trial: bool = False, trial_days: Optional[int] = None):
    """Track subscription creation - inactive event."""
    track_inactive_event(
        user_id,
        "Stripe Subscription Created",
        {
            "subscription_id": subscription_id,
            "plan_name": plan_name,
            "amount": amount,
            "currency": currency,
            "is_trial": is_trial,
            "trial_days": trial_days
        }
    )
    
    # Update user properties
    identify_user(user_id, {
        "subscription_status": "trialing" if is_trial else "active",
        "subscription_plan": plan_name,
        "subscription_created_at": datetime.utcnow().isoformat(),
        "is_paying_customer": True,
        "subscription_amount": amount
    })

def track_subscription_cancelled(user_id: str, subscription_id: str, 
                               plan_name: Optional[str] = None,
                               cancel_reason: Optional[str] = None,
                               subscription_length_days: Optional[int] = None):
    """Track subscription cancellation - inactive event."""
    track_inactive_event(
        user_id,
        "Stripe Subscription Cancelled",
        {
            "subscription_id": subscription_id,
            "plan_name": plan_name,
            "cancel_reason": cancel_reason,
            "subscription_length_days": subscription_length_days
        }
    )
    
    # Update user properties
    identify_user(user_id, {
        "subscription_status": "cancelled",
        "subscription_plan": None,
        "is_paying_customer": False,
        "subscription_cancelled_at": datetime.utcnow().isoformat(),
        "churn_reason": cancel_reason
    })

def track_subscription_reactivated(user_id: str, subscription_id: str,
                                 plan_name: Optional[str] = None):
    """Track subscription reactivation - inactive event."""
    track_inactive_event(
        user_id,
        "Stripe Subscription Reactivated",
        {
            "subscription_id": subscription_id,
            "plan_name": plan_name
        }
    )
    
    # Update user properties
    identify_user(user_id, {
        "subscription_status": "active",
        "subscription_plan": plan_name,
        "is_paying_customer": True,
        "subscription_reactivated_at": datetime.utcnow().isoformat()
    })

def track_checkout_completed(user_id: str, session_id: str, amount: float,
                           currency: str = "USD", plan_name: Optional[str] = None):
    """Track completed checkout - inactive event."""
    track_inactive_event(
        user_id,
        "Stripe Checkout Completed",
        {
            "session_id": session_id,
            "amount": amount,
            "currency": currency,
            "plan_name": plan_name
        }
    )
    
    # Update user properties
    identify_user(user_id, {
        "last_checkout_completed": datetime.utcnow().isoformat(),
        "checkout_amount": amount,
        "checkout_plan": plan_name
    })

def track_trial_ended(user_id: str, subscription_id: str, plan_name: Optional[str] = None,
                    converted_to_paid: bool = False):
    """Track trial ending - inactive event."""
    track_inactive_event(
        user_id,
        "Stripe Trial Ended",
        {
            "subscription_id": subscription_id,
            "plan_name": plan_name,
            "converted_to_paid": converted_to_paid
        }
    )
    
    # Update user properties
    identify_user(user_id, {
        "trial_ended_at": datetime.utcnow().isoformat(),
        "trial_converted": converted_to_paid,
        "subscription_status": "active" if converted_to_paid else "trial_ended"
    })