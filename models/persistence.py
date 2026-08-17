"""Validated immutable records for persisted decision evidence and audit history."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from models.decision_intelligence import (
    DecisionFacts,
    LLMDecisionProposal,
    PolicyValidationResult,
    ReferenceValidationResult,
)
from models.decision_workflow import DecisionWorkflowStatus
from models.what_if import WhatIfComparisonResult, WhatIfScenario


class AuditEventType(str, Enum):
    DECISION_CREATED = "DECISION_CREATED"
    DECISION_VIEWED = "DECISION_VIEWED"
    DECISION_APPROVED = "DECISION_APPROVED"
    DECISION_REJECTED = "DECISION_REJECTED"
    WHAT_IF_CREATED = "WHAT_IF_CREATED"
    WHAT_IF_VIEWED = "WHAT_IF_VIEWED"
    SUBSCRIPTION_CHECKOUT_COMPLETED = "SUBSCRIPTION_CHECKOUT_COMPLETED"
    SUBSCRIPTION_STATUS_UPDATED = "SUBSCRIPTION_STATUS_UPDATED"
    SUBSCRIPTION_CANCELED = "SUBSCRIPTION_CANCELED"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    INVENTORY_VOICE_MUTATION = "INVENTORY_VOICE_MUTATION"
    INVENTORY_CAMERA_RECONCILIATION = "INVENTORY_CAMERA_RECONCILIATION"
    INVENTORY_STOCK_ADJUSTMENT = "INVENTORY_STOCK_ADJUSTMENT"

class SavedDecisionReview(BaseModel):
    """A read-only persisted decision snapshot and its optional reasoning evidence."""

    snapshot_id: str = Field(min_length=64, max_length=64)
    business_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    facts: DecisionFacts
    status: DecisionWorkflowStatus
    created_at: datetime
    proposal: LLMDecisionProposal | None = None
    reference_validation: ReferenceValidationResult | None = None
    policy_validation: PolicyValidationResult | None = None

    @model_validator(mode="after")
    def validate_snapshot_relationships(self) -> "SavedDecisionReview":
        if self.snapshot_id != self.facts.snapshot_id:
            raise ValueError("saved snapshot_id must match immutable DecisionFacts")
        if self.business_id != self.facts.business.business_id:
            raise ValueError("saved business_id must match DecisionFacts")
        if self.product_id != self.facts.business.product_id:
            raise ValueError("saved product_id must match DecisionFacts")
        return self


class SavedWhatIfScenario(BaseModel):
    """A read-only scenario and deterministic comparison tied to one baseline."""

    id: str = Field(min_length=1)
    decision_snapshot_id: str = Field(min_length=64, max_length=64)
    baseline_snapshot_id: str = Field(min_length=64, max_length=64)
    scenario: WhatIfScenario
    comparison: WhatIfComparisonResult
    created_at: datetime

    @model_validator(mode="after")
    def validate_baseline_relationships(self) -> "SavedWhatIfScenario":
        if self.scenario.scenario_id != self.comparison.scenario_id:
            raise ValueError("saved scenario must match comparison scenario_id")
        if self.baseline_snapshot_id != self.comparison.baseline_snapshot_id:
            raise ValueError("saved baseline must match comparison baseline_snapshot_id")
        return self


class AuditEvent(BaseModel):
    """A non-secret, append-only record of review activity."""

    id: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    event_type: AuditEventType
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime


class AdminAuditEvent(BaseModel):
    """An immutable, append-only security and administrative audit record."""

    id: str = Field(min_length=1)
    user_id: str | None = None
    user_email: str | None = None
    event_type: str = Field(min_length=1)
    entity_type: str = Field(default="SYSTEM")
    entity_id: str = Field(default="NONE")
    metadata_json: str = Field(default="{}")
    ip_address: str | None = None
    user_agent: str | None = None
    security_classification: str = Field(default="STANDARD")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UserActivityEvent(BaseModel):
    """User-visible activity history record."""

    id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    activity_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(default="")
    metadata_json: str = Field(default="{}")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
