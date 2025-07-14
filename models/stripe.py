# models/stripe.py
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class PlanType(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"

class CreateCheckoutSessionRequest(BaseModel):
    priceId: str
    successUrl: str
    cancelUrl: str
    userId: str
    userEmail: str

class CreateCheckoutSessionResponse(BaseModel):
    success: bool
    sessionId: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None

class SubscriptionStatusResponse(BaseModel):
    isActive: bool
    planId: Optional[str] = None
    currentPeriodEnd: Optional[str] = None
    cancelAtPeriodEnd: bool = False
    stripeCustomerId: Optional[str] = None
    stripeSubscriptionId: Optional[str] = None

class CancelSubscriptionRequest(BaseModel):
    userId: str

class CustomerPortalRequest(BaseModel):
    userId: str
    returnUrl: str

class CustomerPortalResponse(BaseModel):
    success: bool
    url: Optional[str] = None
    error: Optional[str] = None

class VerifySessionRequest(BaseModel):
    sessionId: str

class VerifySessionResponse(BaseModel):
    success: bool
    subscription: Optional[SubscriptionStatusResponse] = None
    error: Optional[str] = None

class PricingPlan(BaseModel):
    id: str
    name: str
    price: float
    currency: str
    interval: str
    priceId: str

class PricingResponse(BaseModel):
    success: bool
    plans: Optional[List[PricingPlan]] = None
    error: Optional[str] = None

class WebhookEvent(BaseModel):
    id: str
    type: str
    data: dict
    created: int