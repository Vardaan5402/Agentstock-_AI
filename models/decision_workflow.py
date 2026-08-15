"""Typed inputs and review-only results for the Milestone 7 decision workflow."""

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from models.business import Business
from models.decision_intelligence import (
    DecisionFacts,
    DecisionReviewPacket,
    LLMDecisionProposal,
    PolicyValidationResult,
    ReferenceValidationResult,
)
from models.inventory import Product
from models.policy import Policy
from models.supplier import Supplier, SupplierProduct
from models.what_if import BusinessScenarioBaseline, BusinessScenarioOutcome


class DecisionWorkflowStatus(str, Enum):
    """Safe presentation states for a review-only decision run."""

    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    REASONING_UNAVAILABLE = "REASONING_UNAVAILABLE"
    REASONING_REJECTED = "REASONING_REJECTED"
    POLICY_REVIEW_REQUIRED = "POLICY_REVIEW_REQUIRED"


class DecisionWorkflowInput(BaseModel):
    """Validated user-supplied state for one product decision review."""

    business: Business
    product: Product
    policy: Policy
    suppliers: tuple[Supplier, ...] = Field(min_length=1)
    supplier_products: tuple[SupplierProduct, ...] = Field(min_length=1)
    available_budget: float = Field(ge=0)
    simulation_days: int = Field(default=14, ge=0)

    @model_validator(mode="after")
    def validate_reviewable_relationships(self) -> "DecisionWorkflowInput":
        if self.product.business_id != self.business.id:
            raise ValueError("product must belong to the workflow business")
        if self.policy.business_id != self.business.id:
            raise ValueError("policy must belong to the workflow business")
        if not self.policy.require_approval:
            raise ValueError("workflow purchase policies must require human approval")
        supplier_ids = {supplier.id for supplier in self.suppliers}
        if len(supplier_ids) != len(self.suppliers):
            raise ValueError("workflow supplier IDs must be unique")
        if any(supplier.business_id != self.business.id for supplier in self.suppliers):
            raise ValueError("every supplier must belong to the workflow business")
        valid_pairs = {(term.supplier_id, term.product_id) for term in self.supplier_products}
        if not any(pair[1] == self.product.id and pair[0] in supplier_ids for pair in valid_pairs):
            raise ValueError("at least one supplier term must apply to the workflow product")
        return self


class DecisionWorkflowResult(BaseModel):
    """Complete evidence bundle; it deliberately contains no execution capability."""

    status: DecisionWorkflowStatus
    status_detail: str
    baseline: BusinessScenarioBaseline
    baseline_outcome: BusinessScenarioOutcome
    decision_risk_supplier_id: str = Field(min_length=1)
    facts: DecisionFacts
    proposal: LLMDecisionProposal | None = None
    reference_validation: ReferenceValidationResult | None = None
    policy_validation: PolicyValidationResult | None = None
    review_packet: DecisionReviewPacket | None = None
