"""Deterministic policy checks for structured decision proposals."""

from core.simulator import SimulationActionType
from models.decision_intelligence import (
    DecisionFacts,
    LLMDecisionProposal,
    PolicyValidationResult,
    PolicyViolationCode,
)


def validate_decision_policy(
    facts: DecisionFacts, proposal: LLMDecisionProposal
) -> PolicyValidationResult:
    """Evaluate policy without approving or executing a purchase."""
    violations: list[PolicyViolationCode] = []
    if facts.policy.business_id != facts.business.business_id:
        violations.append(PolicyViolationCode.POLICY_BUSINESS_MISMATCH)

    simulations = {simulation.scenario_id: simulation for simulation in facts.simulations}
    selected = simulations.get(proposal.selected_scenario_id)
    if selected is None:
        violations.append(PolicyViolationCode.UNKNOWN_SCENARIO)
        return PolicyValidationResult(
            compliant=False,
            requires_human_approval=True,
            violations=tuple(violations),
            selected_scenario_id=proposal.selected_scenario_id,
        )

    if selected.action_type is SimulationActionType.DO_NOTHING:
        return PolicyValidationResult(
            compliant=not violations,
            requires_human_approval=False,
            violations=tuple(violations),
            selected_scenario_id=proposal.selected_scenario_id,
        )

    option_id = selected.scenario_id.removeprefix("PURCHASE_")
    option = next(
        (item for item in facts.purchase_options if item.option_id == option_id), None
    )
    if option is None or not (
        option.financially_feasible and option.operationally_feasible and option.feasible
    ):
        violations.append(PolicyViolationCode.INFEASIBLE_PURCHASE)
    if selected.purchase_cost > facts.policy.max_auto_purchase:
        violations.append(PolicyViolationCode.AUTO_PURCHASE_LIMIT_EXCEEDED)
    if "PURCHASE" not in facts.policy.allowed_auto_actions:
        violations.append(PolicyViolationCode.ACTION_NOT_ALLOWED)

    return PolicyValidationResult(
        compliant=not violations,
        requires_human_approval=facts.policy.require_approval or bool(violations),
        violations=tuple(violations),
        selected_scenario_id=proposal.selected_scenario_id,
    )
