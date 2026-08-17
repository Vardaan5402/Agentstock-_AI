"""Subscription, Plan Tiers, and Entitlement data models for AgentStock AI."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SubscriptionStatus(str, Enum):
    """Subscription lifecycle statuses."""
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    INACTIVE = "inactive"


class PlanTier(str, Enum):
    """AgentStock AI Subscription Tiers."""
    FREE = "FREE"
    STARTER = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    ENTERPRISE = "ENTERPRISE"


class BillingCycle(str, Enum):
    """Billing cycle frequency."""
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class UserSubscription(BaseModel):
    """User subscription state synchronized via Razorpay and persisted in database."""
    id: str
    user_id: str
    razorpay_customer_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    razorpay_subscription_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    plan_name: str = PlanTier.FREE.value
    billing_cycle: str = BillingCycle.MONTHLY.value
    subscription_status: str = SubscriptionStatus.INACTIVE.value
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False
    minimum_commitment_end: Optional[str] = None
    coupon_code: Optional[str] = None
    discount_applied: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_active(self) -> bool:
        """Return whether subscription provides active paid access."""
        return self.subscription_status in {SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value}


class UsageRecord(BaseModel):
    """Monthly metered usage record for subscription limits."""
    id: str
    user_id: str
    period_month: str  # YYYY-MM
    camera_scans: int = 0
    voice_queries: int = 0
    ai_decisions: int = 0
    documents_analyzed: int = 0
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
