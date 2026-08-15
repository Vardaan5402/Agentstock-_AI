"""Review-only orchestration of AgentStock's existing deterministic engines."""

from core.decision_context import (
    build_decision_facts,
    build_review_packet,
    validate_proposal_references,
)
from core.gemini_reasoner import StructuredReasoner, request_structured_decision
from core.policy_validation import validate_decision_policy
from core.what_if import build_business_scenario_baseline, evaluate_baseline
from models.decision_workflow import (
    DecisionWorkflowInput,
    DecisionWorkflowResult,
    DecisionWorkflowStatus,
)


def run_decision_workflow(
    workflow_input: DecisionWorkflowInput,
    reasoner: StructuredReasoner | None = None,
) -> DecisionWorkflowResult:
    """Create a deterministic review bundle and optionally validate Gemini reasoning.

    The workflow delegates every inventory, supplier, and simulation calculation to
    the existing Milestones 2–6 engines. A missing or failed reasoner never
    prevents deterministic evidence from being returned.
    """
    baseline = build_business_scenario_baseline(
        workflow_input.business,
        workflow_input.product,
        workflow_input.suppliers,
        workflow_input.supplier_products,
        workflow_input.available_budget,
        workflow_input.simulation_days,
    )
    baseline_outcome = evaluate_baseline(baseline)

    # DecisionFacts currently has one inventory-risk field. Use the fastest
    # available supplier deterministically for that shared risk summary; every
    # supplier-specific risk remains present in baseline_outcome as evidence.
    risk_outcome = min(
        baseline_outcome.supplier_outcomes,
        key=lambda outcome: (
            outcome.inventory_risk.supplier_lead_time_days,
            outcome.supplier_id,
        ),
    )
    facts = build_decision_facts(
        workflow_input.business,
        workflow_input.policy,
        workflow_input.product.id,
        risk_outcome.inventory_risk,
        list(baseline_outcome.purchase_options),
        list(baseline_outcome.simulations),
    )

    base_result = {
        "baseline": baseline,
        "baseline_outcome": baseline_outcome,
        "decision_risk_supplier_id": risk_outcome.supplier_id,
        "facts": facts,
    }
    if reasoner is None:
        return DecisionWorkflowResult(
            status=DecisionWorkflowStatus.REASONING_UNAVAILABLE,
            status_detail="Gemini reasoning was not requested; deterministic evidence is ready for review.",
            **base_result,
        )

    try:
        proposal = request_structured_decision(facts, reasoner)
    except Exception:
        return DecisionWorkflowResult(
            status=DecisionWorkflowStatus.REASONING_UNAVAILABLE,
            status_detail="Gemini reasoning is unavailable; deterministic evidence is ready for review.",
            **base_result,
        )

    reference_validation = validate_proposal_references(facts, proposal)
    policy_validation = validate_decision_policy(facts, proposal)
    if not reference_validation.valid:
        return DecisionWorkflowResult(
            status=DecisionWorkflowStatus.REASONING_REJECTED,
            status_detail="Gemini output failed deterministic reference validation and was rejected.",
            proposal=proposal,
            reference_validation=reference_validation,
            policy_validation=policy_validation,
            **base_result,
        )
    if not policy_validation.compliant:
        return DecisionWorkflowResult(
            status=DecisionWorkflowStatus.POLICY_REVIEW_REQUIRED,
            status_detail="Gemini output is evidence-valid but does not satisfy the current policy.",
            proposal=proposal,
            reference_validation=reference_validation,
            policy_validation=policy_validation,
            **base_result,
        )

    packet = build_review_packet(facts, proposal, reference_validation, policy_validation)
    return DecisionWorkflowResult(
        status=DecisionWorkflowStatus.READY_FOR_REVIEW,
        status_detail="Evidence-valid recommendation is ready for human review; no action will be executed.",
        proposal=proposal,
        reference_validation=reference_validation,
        policy_validation=policy_validation,
        review_packet=packet,
        **base_result,
    )
