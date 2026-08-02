"""Deterministic assembly and validation of Milestone 5 decision facts."""

from datetime import datetime

from core.calculations import InventoryRiskResult
from core.constraints import PurchaseOption
from core.simulator import SimulationActionType, SimulationResult
from models.business import Business
from models.decision_intelligence import (
    BusinessDecisionFacts,
    DecisionFacts,
    DecisionReviewPacket,
    EngineVersion,
    LLMDecisionProposal,
    PolicyFacts,
    PolicyValidationResult,
    ReferenceValidationResult,
    UncertaintyCode,
    calculate_snapshot_id,
)
from models.policy import Policy


DEFAULT_ENGINE_VERSIONS = (
    EngineVersion(name="inventory_risk", version="milestone-2"),
    EngineVersion(name="supplier_constraints", version="milestone-3"),
    EngineVersion(name="counterfactual_simulator", version="milestone-4"),
    EngineVersion(name="decision_intelligence", version="milestone-5"),
)


def build_decision_facts(
    business: Business,
    policy: Policy,
    product_id: str,
    inventory_risk: InventoryRiskResult,
    purchase_options: list[PurchaseOption],
    simulations: list[SimulationResult],
    created_at: datetime | None = None,
    engine_versions: tuple[EngineVersion, ...] = DEFAULT_ENGINE_VERSIONS,
) -> DecisionFacts:
    """Build a validated immutable snapshot while preserving every simulation."""
    business_facts = BusinessDecisionFacts(
        business_id=business.id,
        currency=business.currency,
        inventory_budget=business.inventory_budget,
        product_id=product_id,
    )
    policy_facts = PolicyFacts(
        policy_id=policy.id,
        business_id=policy.business_id,
        max_auto_purchase=policy.max_auto_purchase,
        require_approval=policy.require_approval,
        allowed_auto_actions=tuple(policy.allowed_auto_actions),
    )
    options = tuple(purchase_options)
    all_simulations = tuple(simulations)
    eligible = ("DO_NOTHING",) + tuple(
        f"PURCHASE_{option.option_id}"
        for option in options
        if option.financially_feasible
        and option.operationally_feasible
        and option.feasible
    )
    payload = {
        "business": business_facts.model_dump(mode="json"),
        "policy": policy_facts.model_dump(mode="json"),
        "inventory_risk": inventory_risk.model_dump(mode="json"),
        "purchase_options": [option.model_dump(mode="json") for option in options],
        "simulations": [simulation.model_dump(mode="json") for simulation in all_simulations],
        "eligible_scenario_ids": list(eligible),
        "engine_versions": [version.model_dump(mode="json") for version in engine_versions],
    }
    fact_values = {
        "snapshot_id": calculate_snapshot_id(payload),
        "business": business_facts,
        "policy": policy_facts,
        "inventory_risk": inventory_risk,
        "purchase_options": options,
        "simulations": all_simulations,
        "eligible_scenario_ids": eligible,
        "engine_versions": engine_versions,
    }
    if created_at is not None:
        fact_values["created_at"] = created_at
    return DecisionFacts(**fact_values)


def resolve_fact_reference(facts: DecisionFacts, reference: str) -> object:
    """Resolve an advisory stable fact path or raise ``ValueError``.

    Supported paths are rooted at ``/business``, ``/policy``,
    ``/inventory_risk``, ``/purchase_options/{option_id}``, or
    ``/simulations/{scenario_id}``. Scenario and option IDs avoid brittle list
    indexes and make references auditable across presentation layers.
    """
    if not reference.startswith("/"):
        raise ValueError("fact reference must start with '/'")
    parts = [part for part in reference.split("/")[1:] if part]
    if not parts:
        raise ValueError("fact reference cannot be empty")

    if parts[0] == "purchase_options":
        if len(parts) < 2:
            raise ValueError("purchase option reference requires an option ID")
        source = {
            option.option_id: option.model_dump(mode="json")
            for option in facts.purchase_options
        }
        return _resolve_path(source, parts[1:])
    if parts[0] == "simulations":
        if len(parts) < 2:
            raise ValueError("simulation reference requires a scenario ID")
        source = {
            simulation.scenario_id: simulation.model_dump(mode="json")
            for simulation in facts.simulations
        }
        return _resolve_path(source, parts[1:])
    if parts[0] in {"business", "policy", "inventory_risk"}:
        source = facts.model_dump(mode="json")[parts[0]]
        return _resolve_path(source, parts[1:])
    raise ValueError("fact reference root is not allowed")


def validate_proposal_references(
    facts: DecisionFacts, proposal: LLMDecisionProposal
) -> ReferenceValidationResult:
    """Verify Gemini's selection and advisory references without trusting them."""
    errors: list[str] = []
    known_scenarios = {simulation.scenario_id for simulation in facts.simulations}
    if proposal.selected_scenario_id not in facts.eligible_scenario_ids:
        errors.append("selected_scenario_id is not eligible")

    for claim_index, claim in enumerate(proposal.reasoning_claims):
        for scenario_id in claim.compared_scenario_ids:
            if scenario_id not in known_scenarios:
                errors.append(f"reasoning_claims[{claim_index}] references an unknown scenario")
        for reference in claim.fact_references:
            try:
                resolve_fact_reference(facts, reference)
            except ValueError as error:
                errors.append(f"invalid fact reference '{reference}': {error}")

    required_uncertainties = derive_required_uncertainties(
        facts, proposal.selected_scenario_id
    )
    supplied_uncertainties = set(proposal.uncertainty_codes)
    missing_uncertainties = required_uncertainties - supplied_uncertainties
    if missing_uncertainties:
        errors.append("proposal omits required deterministic uncertainty codes")

    return ReferenceValidationResult(
        valid=not errors,
        errors=tuple(errors),
        selected_scenario_id=proposal.selected_scenario_id,
    )


def derive_required_uncertainties(
    facts: DecisionFacts, selected_scenario_id: str
) -> set[UncertaintyCode]:
    """Derive warnings from facts; Gemini cannot suppress these conditions."""
    required: set[UncertaintyCode] = set()
    if facts.inventory_risk.runway_days is None:
        required.add(UncertaintyCode.ZERO_DEMAND_FORECAST)
    purchase_options = facts.purchase_options
    if not any(option.feasible for option in purchase_options):
        required.add(UncertaintyCode.NO_FEASIBLE_PURCHASE_OPTION)
    simulation = next(
        (item for item in facts.simulations if item.scenario_id == selected_scenario_id),
        None,
    )
    if (
        simulation is not None
        and simulation.action_type is SimulationActionType.PURCHASE
        and simulation.stockout_day is not None
        and simulation.arrival_day is not None
        and simulation.arrival_day > simulation.stockout_day
    ):
        required.add(UncertaintyCode.LATE_ARRIVAL_STOCKOUT)
    return required


def build_review_packet(
    facts: DecisionFacts,
    proposal: LLMDecisionProposal,
    reference_validation: ReferenceValidationResult,
    policy_validation: PolicyValidationResult,
) -> DecisionReviewPacket:
    """Package review information only; it deliberately performs no action."""
    return DecisionReviewPacket(
        facts=facts,
        proposal=proposal,
        reference_validation=reference_validation,
        policy_validation=policy_validation,
    )


def _resolve_path(source: object, parts: list[str]) -> object:
    current = source
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            raise ValueError("path does not resolve to a deterministic fact")
        current = current[part]
    return current
