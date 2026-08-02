"""Validated models for deterministic business what-if simulations."""

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.calculations import InventoryRiskResult
from core.constraints import PurchaseOption
from core.simulator import SimulationResult
from models.business import Business
from models.decision_intelligence import (
    DecisionConfidence,
    ReasoningConclusion,
    ReasoningDimension,
    UncertaintyCode,
)
from models.inventory import Product
from models.supplier import Supplier, SupplierProduct


class AdjustmentMode(str, Enum):
    SET = "SET"
    DELTA = "DELTA"
    PERCENTAGE = "PERCENTAGE"


class ShockTarget(str, Enum):
    DEMAND = "DEMAND"
    INVENTORY = "INVENTORY"
    AVAILABLE_BUDGET = "AVAILABLE_BUDGET"
    SUPPLIER_LEAD_TIME = "SUPPLIER_LEAD_TIME"
    SUPPLIER_PRICE = "SUPPLIER_PRICE"
    MOQ = "MOQ"
    SUPPLIER_RELIABILITY = "SUPPLIER_RELIABILITY"


SUPPLIER_TARGETS = {
    ShockTarget.SUPPLIER_LEAD_TIME,
    ShockTarget.SUPPLIER_PRICE,
    ShockTarget.MOQ,
    ShockTarget.SUPPLIER_RELIABILITY,
}


class NumericShock(BaseModel):
    """A controlled numeric modification to one baseline field."""

    target: ShockTarget
    mode: AdjustmentMode
    value: float
    supplier_id: str | None = None

    @model_validator(mode="after")
    def validate_target_scope(self) -> "NumericShock":
        if self.target in SUPPLIER_TARGETS and not self.supplier_id:
            raise ValueError("supplier-level shocks require supplier_id")
        if self.target not in SUPPLIER_TARGETS and self.supplier_id is not None:
            raise ValueError("product-level shocks must not include supplier_id")
        return self


class WhatIfScenario(BaseModel):
    """A named set of non-conflicting user-defined changes."""

    scenario_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    shocks: tuple[NumericShock, ...]
    description: str | None = None

    @model_validator(mode="after")
    def validate_unique_targets(self) -> "WhatIfScenario":
        keys = [(shock.target, shock.supplier_id) for shock in self.shocks]
        if len(keys) != len(set(keys)):
            raise ValueError("scenario contains conflicting shocks for the same target")
        return self


class AppliedShock(BaseModel):
    """Auditable evidence of one deterministic baseline-to-derived change."""

    target: ShockTarget
    mode: AdjustmentMode
    supplier_id: str | None = None
    baseline_value: float
    requested_value: float
    derived_value: float


class BusinessScenarioBaseline(BaseModel):
    """An immutable source state used to derive every counterfactual."""

    model_config = ConfigDict(frozen=True)

    baseline_snapshot_id: str = Field(min_length=64, max_length=64)
    business: Business
    product: Product
    suppliers: tuple[Supplier, ...]
    supplier_products: tuple[SupplierProduct, ...]
    available_budget: float = Field(ge=0)
    simulation_days: int = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_integrity_and_snapshot(self) -> "BusinessScenarioBaseline":
        if self.business.id != self.product.business_id:
            raise ValueError("product must belong to the baseline business")
        supplier_ids = [supplier.id for supplier in self.suppliers]
        if len(supplier_ids) != len(set(supplier_ids)):
            raise ValueError("baseline supplier IDs must be unique")
        suppliers = {supplier.id: supplier for supplier in self.suppliers}
        for terms in self.supplier_products:
            if terms.product_id != self.product.id:
                raise ValueError("supplier product must belong to the baseline product")
            supplier = suppliers.get(terms.supplier_id)
            if supplier is None or supplier.business_id != self.business.id:
                raise ValueError("supplier product must reference a baseline business supplier")
        if self.baseline_snapshot_id != calculate_baseline_snapshot_id(self.snapshot_payload()):
            raise ValueError("baseline_snapshot_id does not match canonical baseline facts")
        return self

    def snapshot_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"baseline_snapshot_id", "created_at"})

    def canonical_json(self) -> str:
        return canonical_json(self.model_dump(mode="json"))


class CounterfactualBusinessState(BaseModel):
    """A derived state; it never mutates the immutable baseline."""

    model_config = ConfigDict(frozen=True)

    baseline_snapshot_id: str = Field(min_length=64, max_length=64)
    scenario_id: str = Field(min_length=1)
    derived_product: Product
    derived_suppliers: tuple[Supplier, ...]
    derived_supplier_products: tuple[SupplierProduct, ...]
    derived_available_budget: float = Field(ge=0)
    applied_shocks: tuple[AppliedShock, ...]


class SupplierOutcome(BaseModel):
    """The deterministic outcome for one supplier/product relationship."""

    supplier_id: str = Field(min_length=1)
    inventory_risk: InventoryRiskResult
    purchase_option: PurchaseOption
    simulation_result: SimulationResult


class BusinessScenarioOutcome(BaseModel):
    """Complete evaluation of one baseline or counterfactual business state."""

    baseline_snapshot_id: str = Field(min_length=64, max_length=64)
    scenario_id: str = Field(min_length=1)
    derived_state: CounterfactualBusinessState
    purchase_options: tuple[PurchaseOption, ...]
    simulations: tuple[SimulationResult, ...]
    supplier_outcomes: tuple[SupplierOutcome, ...]


class MetricDelta(BaseModel):
    """A deterministic before/after metric comparison."""

    baseline_value: float | str | bool | None
    counterfactual_value: float | str | bool | None
    numeric_change: float | None = None


class SupplierOutcomeComparison(BaseModel):
    """Unranked comparison for the same supplier across two states."""

    supplier_id: str = Field(min_length=1)
    runway_days: MetricDelta
    stockout_risk: MetricDelta
    stockout_day: MetricDelta
    total_shortage_units: MetricDelta
    purchase_quantity: MetricDelta
    purchase_cost: MetricDelta
    budget_remaining: MetricDelta
    coverage_gap: MetricDelta
    operational_feasibility: MetricDelta
    financial_feasibility: MetricDelta
    supplier_reliability: MetricDelta


class WhatIfComparisonResult(BaseModel):
    """A deterministic baseline-versus-counterfactual comparison artifact."""

    baseline_snapshot_id: str = Field(min_length=64, max_length=64)
    scenario_id: str = Field(min_length=1)
    baseline_outcome: BusinessScenarioOutcome
    counterfactual_outcome: BusinessScenarioOutcome
    supplier_comparisons: tuple[SupplierOutcomeComparison, ...]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WhatIfExplanationClaim(BaseModel):
    """A qualitative Gemini explanation claim with advisory fact references."""

    dimension: ReasoningDimension
    conclusion: ReasoningConclusion
    supplier_ids: tuple[str, ...] = ()
    fact_references: tuple[str, ...] = ()


class WhatIfExplanation(BaseModel):
    """Narrow LLM output; no numerical business facts can be returned."""

    scenario_id: str = Field(min_length=1)
    explanation_claims: tuple[WhatIfExplanationClaim, ...] = ()
    uncertainty_codes: tuple[UncertaintyCode, ...] = ()
    confidence: DecisionConfidence
    uncertainty_note: str | None = None


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def calculate_baseline_snapshot_id(payload: dict[str, object]) -> str:
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()
