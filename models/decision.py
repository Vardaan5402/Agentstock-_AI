"""Decision ledger models."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class DecisionStatus(str, Enum):
    """Allowed lifecycle states for an inventory decision."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class DecisionOption(BaseModel):
    """One candidate response to an inventory problem."""

    option_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    supplier_id: str | None = None
    quantity: int = Field(ge=0)
    unit_cost: float = Field(ge=0)
    total_cost: float = Field(ge=0)
    projected_runway_days: float = Field(ge=0)
    stockout_risk: str = Field(min_length=1)
    budget_remaining: float = Field(ge=0)


class Decision(BaseModel):
    """A validated decision and its available options."""

    id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    problem: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    options: list[DecisionOption]
    recommended_option_id: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    requires_approval: bool
    status: DecisionStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def recommended_option_must_exist(self) -> "Decision":
        """Ensure the recommendation identifies one of this decision's options."""
        option_ids = {option.option_id for option in self.options}
        if self.recommended_option_id not in option_ids:
            raise ValueError("recommended_option_id must match a supplied option")
        return self


class Outcome(BaseModel):
    """The verified result of an executed decision."""

    id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    actual_result: str | None = None
    success: bool | None = None
    verified_at: datetime | None = None
