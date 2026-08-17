"""Business domain model."""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class Business(BaseModel):
    """A business whose inventory data is managed by AgentStock."""

    id: str = Field(min_length=1)
    user_id: Optional[str] = None
    name: str = Field(min_length=1)
    proprietor_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    country: str = Field(default="IN", min_length=1)
    city: Optional[str] = None
    currency: str = Field(default="INR", min_length=1)
    industry: str = Field(default="Retail", min_length=1)
    business_type: Optional[str] = None
    google_maps_location: Optional[str] = None
    inventory_category: Optional[str] = None
    inventory_budget: float = Field(default=0.0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
