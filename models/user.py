"""User and Authentication Domain Models."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """Role-based access control roles."""
    ADMIN = "ADMIN"
    BUSINESS_OWNER = "BUSINESS_OWNER"
    USER = "USER"


class User(BaseModel):
    """User account entity with enterprise multi-tenant & security fields."""
    id: str
    name: str
    email: str
    password_hash: str
    role: str = UserRole.USER.value
    phone: Optional[str] = None
    preferred_language: str = "en"
    preferred_currency: str = "INR"
    timezone: str = "UTC"
    profile_image_path: Optional[str] = None
    is_verified: bool = True
    is_locked: bool = False
    failed_login_attempts: int = 0
    locked_until: Optional[str] = None
    terms_accepted_at: Optional[str] = None
    privacy_accepted_at: Optional[str] = None
    aup_accepted_at: Optional[str] = None
    onboarding_completed: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value

    @property
    def has_accepted_legal(self) -> bool:
        return bool(self.terms_accepted_at and self.privacy_accepted_at and self.aup_accepted_at)


class OTPRecord(BaseModel):
    """Email OTP verification code record with cryptographically secure metadata."""
    email: str
    otp_hash: str
    expires_at: str
    attempts: int = 0
    max_attempts: int = 5
    last_sent_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
