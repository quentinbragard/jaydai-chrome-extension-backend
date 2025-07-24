# services/stripe/webhooks/process_webhook_event.py - Updated with Amplitude tracking
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from supabase import Client
import stripe
from services.stripe.subscriptions import update_subscription_status
from services.stripe.helpers import _get_plan_name_from_product_id
from utils.amplitude_events import (
    track_payment_succeeded,
    track_payment_failed,
    track_subscription_created,
    track_subscription_cancelled,
    track_subscription_reactivated,
    track_checkout_completed
)

logger = logging.getLogger(__name__)

async def process_webhook_event(supabase: Client, event_id: str, event_type: str, event_data: Dict[str, Any]) -> bool:
    """Process webhook events with essential Stripe Amplitude tracking only."""
    handlers = {
        # Core subscription events
        "customer.subscription.created": _handle_subscription_created,
        "customer.subscription.updated": _handle_subscription_updated,
        "customer.subscription.deleted": _handle_subscription_deleted,
        
        # Payment events
        "invoice.payment_succeeded": _handle_payment_succeeded,
        "invoice.payment_failed": _handle_payment_failed,
        
        # Checkout events
        "checkout.session.completed": _handle_checkout_completed,
    }
    
    handler = handlers.get(event_type)
    if handler:
        return await handler(supabase, event_id, event_data.get("object", {}))
    
    # For unhandled events, just return True (no tracking)
    logger.info(f"No handler for event type: {event_type}")
    return True

def _extract_user_id(obj: Dict[str, Any]) -> Optional[str]:
    """Extract user_id from various Stripe object types."""
    # Try metadata first
    if metadata := obj.get("metadata", {}):
        if user_id := metadata.get("user_id"):
            return user_id
    
    # Try subscription metadata for invoice objects
    if subscription_id := obj.get("subscription"):
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return subscription.metadata.get("user_id")
        except stripe.error.StripeError:
            pass
    
    return None

def _get_subscription_details(subscription: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key subscription details."""
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return {}
    
    item = items[0]
    price = item.get("price", {})
    product_id = price.get("product", "")
    
    return {
        "subscription_id": subscription.get("id"),
        "plan_name": _get_plan_name_from_product_id(product_id),
        "amount": price.get("unit_amount", 0) / 100 if price.get("unit_amount") else 0,
        "currency": price.get("currency", "usd").upper(),
        "is_trial": bool(subscription.get("trial_end")),
        "trial_days": None
    }

# Subscription Event Handlers
async def _handle_subscription_created(supabase: Client, event_id: str, subscription: Dict[str, Any]):
    """Handle subscription created event."""
    user_id = subscription["metadata"].get("user_id")
    if not user_id:
        logger.warning(f"No user_id found in subscription.created event {event_id}")
        return True
    
    # Update database
    stripe_subscription = stripe.Subscription.construct_from(subscription, stripe.api_key)
    await update_subscription_status(supabase, user_id, stripe_subscription)
    
    # Track in Amplitude
    details = _get_subscription_details(subscription)
    trial_end = subscription.get("trial_end")
    trial_start = subscription.get("trial_start")
    trial_days = None
    
    if trial_end and trial_start:
        trial_days = int((trial_end - trial_start) / 86400)  # Convert seconds to days
    
    track_subscription_created(
        user_id=user_id,
        subscription_id=details["subscription_id"],
        plan_name=details["plan_name"],
        amount=details["amount"],
        currency=details["currency"],
        is_trial=details["is_trial"],
        trial_days=trial_days
    )
    
    logger.info(f"Processed subscription created for user {user_id}")
    return True

async def _handle_subscription_updated(supabase: Client, event_id: str, subscription: Dict[str, Any]):
    """Handle subscription updated event."""
    user_id = subscription["metadata"].get("user_id")
    if not user_id:
        return True
    
    # Update database
    stripe_subscription = stripe.Subscription.construct_from(subscription, stripe.api_key)
    await update_subscription_status(supabase, user_id, stripe_subscription)
    
    # Check if this is a reactivation (cancel_at_period_end changed from True to False)
    if subscription.get("cancel_at_period_end") == False:
        # This might be a reactivation - we could track it, but keeping it simple for now
        details = _get_subscription_details(subscription)
        track_subscription_reactivated(
            user_id=user_id,
            subscription_id=details["subscription_id"],
            plan_name=details["plan_name"]
        )
    
    return True

async def _handle_subscription_deleted(supabase: Client, event_id: str, subscription: Dict[str, Any]):
    """Handle subscription deleted/cancelled event."""
    user_id = subscription["metadata"].get("user_id")
    if not user_id:
        return True
    
    # Update database
    supabase.table("users_metadata").update({
        "subscription_status": "cancelled", 
        "subscription_plan": None
    }).eq("user_id", user_id).execute()
    
    supabase.table("stripe_subscriptions").update({
        "status": "cancelled", 
        "cancelled_at": datetime.now(timezone.utc).isoformat()
    }).eq("user_id", user_id).execute()
    
    # Track in Amplitude
    details = _get_subscription_details(subscription)
    
    # Calculate subscription length if possible
    subscription_length_days = None
    if created := subscription.get("created"):
        subscription_length_days = int((datetime.now().timestamp() - created) / 86400)
    
    track_subscription_cancelled(
        user_id=user_id,
        subscription_id=details["subscription_id"],
        plan_name=details["plan_name"],
        cancel_reason=subscription.get("cancellation_details", {}).get("reason"),
        subscription_length_days=subscription_length_days
    )
    
    logger.info(f"Marked subscription as cancelled for user {user_id}")
    return True

# Payment Event Handlers
async def _handle_payment_succeeded(supabase: Client, event_id: str, invoice: Dict[str, Any]):
    """Handle successful payment event."""
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return True
    
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        user_id = subscription.metadata.get("user_id")
        if not user_id:
            return True
        
        # Update database
        await update_subscription_status(supabase, user_id, subscription)
        
        # Track in Amplitude
        amount = (invoice.get("amount_paid", 0) or 0) / 100
        currency = invoice.get("currency", "usd").upper()
        
        # Get plan name
        items = subscription.get("items", {}).get("data", [])
        plan_name = None
        if items:
            product_id = items[0].get("price", {}).get("product", "")
            plan_name = _get_plan_name_from_product_id(product_id)
        
        track_payment_succeeded(
            user_id=user_id,
            amount=amount,
            currency=currency,
            subscription_id=subscription_id,
            plan_name=plan_name,
            billing_reason=invoice.get("billing_reason"),
            invoice_id=invoice.get("id")
        )
        
        return True
        
    except stripe.error.StripeError as e:
        logger.error(f"Failed to retrieve subscription {subscription_id}: {str(e)}")
        return False

async def _handle_payment_failed(supabase: Client, event_id: str, invoice: Dict[str, Any]):
    """Handle failed payment event."""
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return True
    
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        user_id = subscription.metadata.get("user_id")
        if not user_id:
            return True
        
        # Update database
        await update_subscription_status(supabase, user_id, subscription)
        
        # Track in Amplitude
        amount = (invoice.get("amount_due", 0) or 0) / 100
        currency = invoice.get("currency", "usd").upper()
        
        failure_reason = None
        if last_error := invoice.get("last_finalization_error"):
            failure_reason = last_error.get("message")
        
        track_payment_failed(
            user_id=user_id,
            amount=amount,
            currency=currency,
            subscription_id=subscription_id,
            failure_reason=failure_reason,
            attempt_count=invoice.get("attempt_count", 1)
        )
        
        return True
        
    except stripe.error.StripeError as e:
        logger.error(f"Failed to retrieve subscription {subscription_id}: {str(e)}")
        return False

# Checkout Event Handlers
async def _handle_checkout_completed(supabase: Client, event_id: str, session: Dict[str, Any]):
    """Handle checkout session completed event."""
    user_id = session.get("metadata", {}).get("user_id")
    if not user_id:
        return True
    
    amount = (session.get("amount_total", 0) or 0) / 100
    currency = session.get("currency", "usd").upper()
    
    # Try to get plan name from subscription if available
    plan_name = None
    if subscription_id := session.get("subscription"):
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            items = subscription.get("items", {}).get("data", [])
            if items:
                product_id = items[0].get("price", {}).get("product", "")
                plan_name = _get_plan_name_from_product_id(product_id)
        except:
            pass
    
    track_checkout_completed(
        user_id=user_id,
        session_id=session.get("id"),
        amount=amount,
        currency=currency,
        plan_name=plan_name
    )
    
    return True