"""Policy model for future approval and action controls."""

from pydantic import BaseModel, Field


class Policy(BaseModel):
    """Persisted policy configuration; it does not execute actions."""

    id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    max_auto_purchase: float = Field(default=0.0, ge=0)
    require_approval: bool = True
    allowed_auto_actions: list[str] = Field(default_factory=list)
