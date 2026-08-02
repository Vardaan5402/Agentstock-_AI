"""Business domain model."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Business(BaseModel):
    """A business whose inventory data is managed by AgentStock."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    country: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    inventory_budget: float = Field(default=0.0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
