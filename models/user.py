from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class User(BaseModel):
    """User account entity."""
    id: str
    name: str
    email: str
    password_hash: str
    is_verified: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OTPRecord(BaseModel):
    """Email OTP verification code record."""
    email: str
    otp_code: str
    expires_at: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
