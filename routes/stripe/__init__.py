# routes/stripe/__init__.py
import os
import dotenv
from fastapi import APIRouter
from supabase import create_client, Client
from unittest.mock import MagicMock
from utils.stripe_service import StripeService

dotenv.load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = MagicMock()

# Initialize Stripe service
stripe_service = StripeService(supabase)

router = APIRouter(prefix="/stripe", tags=["Stripe Payment"])

# Import endpoints to register them with the router
from . import (
    create_checkout_session,
    subscription_status,
    cancel_subscription,
    customer_portal,
    verify_session,
    pricing,
    webhook
)

__all__ = [
    "router",
    "supabase",
    "stripe_service",
]