import logging
from typing import Optional
from datetime import datetime
import stripe
from supabase import Client

from services.stripe.helpers import _get_plan_name_from_product_id

logger = logging.getLogger(__name__)

async def update_subscription_status(supabase: Client, user_id: str, subscription: stripe.Subscription, stripe_event_id: Optional[str] = None):
    try:
        product_id = subscription.get('items').get('data')[0].get('plan').get('product')
        plan_name = _get_plan_name_from_product_id(product_id)
        print("👇👇👇👇 plan_name 👇👇👇👇\n")
        print(plan_name)
        data = {
            "user_id": user_id,
            "stripe_customer_id": subscription.get("customer"),
            "stripe_subscription_id": subscription.get("id"),
            "stripe_price_id": subscription.get('items').get('data')[0].get('price').get('id'),
            "stripe_product_id": product_id,
            "status": subscription.get("status"),
            "current_period_start": datetime.fromtimestamp(subscription.get("current_period_start")).isoformat() if subscription.get("current_period_start") else None,
            "current_period_end": datetime.fromtimestamp(subscription.get("current_period_end")).isoformat() if subscription.get("current_period_end") else None,
            "cancel_at_period_end": subscription.get("cancel_at_period_end"),
            "cancelled_at": datetime.fromtimestamp(subscription.get("canceled_at")).isoformat() if subscription.get("canceled_at") else None,
            "trial_start": datetime.fromtimestamp(subscription.get("trial_start")).isoformat() if subscription.get("trial_start") else None,
            "trial_end": datetime.fromtimestamp(subscription.get("trial_end")).isoformat() if subscription.get("trial_end") else None,
            "metadata": subscription.get("metadata") or {},
        }
        existing = supabase.table("stripe_subscriptions").select("id").eq("stripe_subscription_id", subscription.get("id")).execute()
        if existing.data:
            supabase.table("stripe_subscriptions").update(data).eq("stripe_subscription_id", subscription.get("id")).execute()
        else:
            supabase.table("stripe_subscriptions").insert(data).execute()    
        supabase.table("users_metadata").update({"subscription_plan": plan_name}).eq("user_id", user_id).execute()
        logger.info("Updated subscription status for user %s: %s", user_id, subscription.get("status"))
    except Exception as e:
        logger.error("Failed to update subscription status for user %s: %s", user_id, e)
