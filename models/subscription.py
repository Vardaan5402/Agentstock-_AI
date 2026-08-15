"""Subscription and entitlement data models for AgentStock AI."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SubscriptionStatus(str, Enum):
    """Stripe subscription lifecycle statuses."""
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


class UserSubscription(BaseModel):
    """User subscription state persisted in SQLite and synchronized via Stripe."""
    id: str
    user_id: str
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    plan_name: str = PlanTier.FREE.value
    subscription_status: str = SubscriptionStatus.INACTIVE.value
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_active(self) -> bool:
        """Return whether subscription provides active paid access."""
        return self.subscription_status in {SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value}
