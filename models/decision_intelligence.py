"""Structured, auditable models for Milestone 5 decision intelligence."""

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.calculations import InventoryRiskResult
from core.constraints import PurchaseOption
from core.simulator import SimulationActionType, SimulationResult


class ReasoningDimension(str, Enum):
    COST = "COST"
    STOCKOUT_RISK = "STOCKOUT_RISK"
    CASH_IMPACT = "CASH_IMPACT"
    RELIABILITY = "RELIABILITY"
    OPERATIONAL_CONTINUITY = "OPERATIONAL_CONTINUITY"


class ReasoningConclusion(str, Enum):
    FAVORS_SELECTED = "FAVORS_SELECTED"
    TRADEOFF = "TRADEOFF"
    NEUTRAL = "NEUTRAL"
    RISK_FLAG = "RISK_FLAG"


class DecisionConfidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class UncertaintyCode(str, Enum):
    ZERO_DEMAND_FORECAST = "ZERO_DEMAND_FORECAST"
    NO_FEASIBLE_PURCHASE_OPTION = "NO_FEASIBLE_PURCHASE_OPTION"
    LATE_ARRIVAL_STOCKOUT = "LATE_ARRIVAL_STOCKOUT"
    BUDGET_CONSTRAINT = "BUDGET_CONSTRAINT"
    INSUFFICIENT_SIMULATION_HORIZON = "INSUFFICIENT_SIMULATION_HORIZON"
    INPUT_DATA_LIMITATION = "INPUT_DATA_LIMITATION"


class PolicyViolationCode(str, Enum):
    POLICY_BUSINESS_MISMATCH = "POLICY_BUSINESS_MISMATCH"
    UNKNOWN_SCENARIO = "UNKNOWN_SCENARIO"
    INFEASIBLE_PURCHASE = "INFEASIBLE_PURCHASE"
    AUTO_PURCHASE_LIMIT_EXCEEDED = "AUTO_PURCHASE_LIMIT_EXCEEDED"
    ACTION_NOT_ALLOWED = "ACTION_NOT_ALLOWED"


class BusinessDecisionFacts(BaseModel):
    """The minimum business facts relevant to a product decision."""

    model_config = ConfigDict(frozen=True)

    business_id: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    inventory_budget: float = Field(ge=0)
    product_id: str = Field(min_length=1)


class PolicyFacts(BaseModel):
    """An immutable policy snapshot used for deterministic review."""

    model_config = ConfigDict(frozen=True)

    policy_id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    max_auto_purchase: float = Field(ge=0)
    require_approval: bool
    allowed_auto_actions: tuple[str, ...] = ()


class EngineVersion(BaseModel):
    """Identifies the deterministic engine versions behind a fact snapshot."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)


class DecisionFacts(BaseModel):
    """An immutable deterministic snapshot supplied to reasoning and review."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str = Field(min_length=64, max_length=64)
    business: BusinessDecisionFacts
    policy: PolicyFacts
    inventory_risk: InventoryRiskResult
    purchase_options: tuple[PurchaseOption, ...]
    simulations: tuple[SimulationResult, ...]
    eligible_scenario_ids: tuple[str, ...]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    engine_versions: tuple[EngineVersion, ...]

    @model_validator(mode="after")
    def validate_integrity_and_snapshot_id(self) -> "DecisionFacts":
        """Reject snapshots that do not preserve valid deterministic scenarios."""
        if self.policy.business_id != self.business.business_id:
            raise ValueError("policy facts must belong to the business facts")

        option_ids = [option.option_id for option in self.purchase_options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("purchase option IDs must be unique")
        if any(option.product_id != self.business.product_id for option in self.purchase_options):
            raise ValueError("every purchase option must belong to the requested product")

        scenario_ids = [simulation.scenario_id for simulation in self.simulations]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("simulation scenario IDs must be unique")
        simulations = {simulation.scenario_id: simulation for simulation in self.simulations}
        do_nothing = simulations.get("DO_NOTHING")
        if do_nothing is None or do_nothing.action_type is not SimulationActionType.DO_NOTHING:
            raise ValueError("a DO_NOTHING simulation is required")

        expected_purchase_scenarios = {f"PURCHASE_{option.option_id}" for option in self.purchase_options}
        actual_purchase_scenarios = {
            simulation.scenario_id
            for simulation in self.simulations
            if simulation.action_type is SimulationActionType.PURCHASE
        }
        if actual_purchase_scenarios != expected_purchase_scenarios:
            raise ValueError("purchase simulations must map exactly to purchase options")

        for option in self.purchase_options:
            simulation = simulations[f"PURCHASE_{option.option_id}"]
            if (
                simulation.supplier_id != option.supplier_id
                or simulation.purchase_quantity != option.purchase_quantity
                or simulation.purchase_cost != option.total_cost
                or simulation.lead_time_days != option.supplier_lead_time_days
            ):
                raise ValueError("purchase simulation does not match its purchase option")

        expected_eligible = ("DO_NOTHING",) + tuple(
            f"PURCHASE_{option.option_id}"
            for option in self.purchase_options
            if option.financially_feasible
            and option.operationally_feasible
            and option.feasible
        )
        if self.eligible_scenario_ids != expected_eligible:
            raise ValueError("eligible scenarios must be the deterministic feasible subset")

        expected_snapshot_id = calculate_snapshot_id(self.snapshot_payload())
        if self.snapshot_id != expected_snapshot_id:
            raise ValueError("snapshot_id does not match canonical deterministic facts")
        return self

    def snapshot_payload(self) -> dict[str, object]:
        """Return the canonical-ID payload, excluding nondeterministic metadata."""
        return self.model_dump(mode="json", exclude={"snapshot_id", "created_at"})

    def canonical_json(self) -> str:
        """Return canonical JSON for Gemini input and audit comparisons."""
        return canonical_json(self.model_dump(mode="json"))


class ReasoningClaim(BaseModel):
    """A qualitative Gemini claim backed by advisory deterministic references."""

    dimension: ReasoningDimension
    conclusion: ReasoningConclusion
    compared_scenario_ids: tuple[str, ...] = ()
    fact_references: tuple[str, ...] = ()


class LLMDecisionProposal(BaseModel):
    """The intentionally narrow structured output Gemini is allowed to return."""

    selected_scenario_id: str = Field(min_length=1)
    reasoning_claims: tuple[ReasoningClaim, ...] = ()
    confidence: DecisionConfidence
    uncertainty_codes: tuple[UncertaintyCode, ...] = ()
    uncertainty_note: str | None = None


class ReferenceValidationResult(BaseModel):
    """Deterministic verification of Gemini's selection and advisory evidence."""

    valid: bool
    errors: tuple[str, ...] = ()
    selected_scenario_id: str


class PolicyValidationResult(BaseModel):
    """Deterministic policy outcome; it never executes an action."""

    compliant: bool
    requires_human_approval: bool
    violations: tuple[PolicyViolationCode, ...] = ()
    selected_scenario_id: str


class DecisionReviewPacket(BaseModel):
    """An auditable review artifact, deliberately separate from execution."""

    facts: DecisionFacts
    proposal: LLMDecisionProposal
    reference_validation: ReferenceValidationResult
    policy_validation: PolicyValidationResult


def canonical_json(value: object) -> str:
    """Serialize JSON-compatible data into a stable canonical representation."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def calculate_snapshot_id(payload: dict[str, object]) -> str:
    """Create a reproducible SHA-256 ID from canonical deterministic facts."""
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()
