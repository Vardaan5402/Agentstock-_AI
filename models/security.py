"""Security, Alerts, Audit, Rate Limiting, and Coupon models."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SecuritySeverity(str, Enum):
    """Severity levels for security events and alerts."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SecurityAlert(BaseModel):
    """Security event record."""
    id: str
    user_id: Optional[str] = None
    event_type: str
    severity: str = SecuritySeverity.LOW.value
    description: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "OPEN"  # OPEN, INVESTIGATING, RESOLVED
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Coupon(BaseModel):
    """Promotional coupon entity for subscription discounts."""
    id: str
    code: str
    discount_type: str = "PERCENTAGE"  # PERCENTAGE, FIXED
    discount_value: float = Field(gt=0)
    plan_tier: Optional[str] = None  # None applies to all plans
    max_redemptions: int = 100
    times_redeemed: int = 0
    expires_at: Optional[str] = None
    is_active: bool = True
    campaign: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CouponRedemption(BaseModel):
    """Per-user single coupon redemption record."""
    id: str
    coupon_id: str
    user_id: str
    redeemed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UploadedDocument(BaseModel):
    """Uploaded business document record (PDF, invoices, CSV, etc.)."""
    id: str
    business_id: str
    user_id: str
    filename: str
    stored_path: str
    mime_type: str
    file_size_bytes: int
    extracted_items_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UserPolicyConsent(BaseModel):
    """Immutable audit record of explicit user consent to platform legal policies."""
    id: str
    user_id: Optional[str] = None
    email: str
    policy_version: str = "1.0"
    terms_version: str = "1.0"
    privacy_version: str = "1.0"
    acceptable_use_version: str = "1.0"
    subscription_policy_version: str = "1.0"
    communication_policy_version: str = "1.0"
    data_security_policy_version: str = "1.0"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    consent_status: str = "ACCEPTED"
    agreed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
