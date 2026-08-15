"""End-to-end tests for Milestone 7's review-only decision workflow."""

import unittest

from core.decision_workflow import run_decision_workflow
from models.business import Business
from models.decision_intelligence import (
    DecisionConfidence,
    LLMDecisionProposal,
    ReasoningClaim,
    ReasoningConclusion,
    ReasoningDimension,
)
from models.decision_workflow import DecisionWorkflowInput, DecisionWorkflowStatus
from models.inventory import Product
from models.policy import Policy
from models.supplier import Supplier, SupplierProduct
from models.what_if import AdjustmentMode, NumericShock, ShockTarget, WhatIfScenario
from core.what_if import run_what_if


class FakeReasoner:
    def __init__(self, proposal: LLMDecisionProposal | Exception) -> None:
        self.proposal = proposal

    def propose(self, facts):
        if isinstance(self.proposal, Exception):
            raise self.proposal
        return self.proposal


def make_input(*, allowed_actions: list[str] | None = None) -> DecisionWorkflowInput:
    business = Business(
        id="business-1", name="Demo shop", country="IN", currency="INR",
        industry="Retail", inventory_budget=5000,
    )
    product = Product(
        id="product-1", business_id=business.id, sku="MILK-1", name="Milk",
        current_stock=12, unit_cost=100, daily_demand=6, safety_stock=5,
    )
    policy = Policy(
        id="policy-1", business_id=business.id, max_auto_purchase=5000,
        require_approval=True,
        allowed_auto_actions=["PURCHASE"] if allowed_actions is None else allowed_actions,
    )
    suppliers = (
        Supplier(id="fast", business_id=business.id, name="Fast supply", lead_time_days=1, reliability_score=0.9),
        Supplier(id="late", business_id=business.id, name="Late supply", lead_time_days=5, reliability_score=0.8),
        Supplier(id="expensive", business_id=business.id, name="MOQ supply", lead_time_days=2, reliability_score=0.95),
    )
    terms = (
        SupplierProduct(supplier_id="fast", product_id=product.id, unit_price=120, minimum_order_quantity=1),
        SupplierProduct(supplier_id="late", product_id=product.id, unit_price=80, minimum_order_quantity=1),
        SupplierProduct(supplier_id="expensive", product_id=product.id, unit_price=200, minimum_order_quantity=50),
    )
    return DecisionWorkflowInput(
        business=business, product=product, policy=policy, suppliers=suppliers,
        supplier_products=terms, available_budget=5000, simulation_days=7,
    )


def valid_proposal(workflow_input: DecisionWorkflowInput) -> LLMDecisionProposal:
    result = run_decision_workflow(workflow_input)
    selected = next(item for item in result.facts.eligible_scenario_ids if item != "DO_NOTHING")
    option_id = selected.removeprefix("PURCHASE_")
    return LLMDecisionProposal(
        selected_scenario_id=selected,
        confidence=DecisionConfidence.MEDIUM,
        reasoning_claims=(
            ReasoningClaim(
                dimension=ReasoningDimension.OPERATIONAL_CONTINUITY,
                conclusion=ReasoningConclusion.FAVORS_SELECTED,
                compared_scenario_ids=("DO_NOTHING", selected),
                fact_references=(
                    f"/purchase_options/{option_id}/coverage_gap",
                    f"/simulations/{selected}/stockout_day",
                ),
            ),
        ),
    )


class DecisionWorkflowTests(unittest.TestCase):
    def test_returns_deterministic_evidence_without_reasoner(self) -> None:
        first = run_decision_workflow(make_input())
        second = run_decision_workflow(make_input())
        self.assertEqual(first.status, DecisionWorkflowStatus.REASONING_UNAVAILABLE)
        self.assertEqual(first.facts.snapshot_id, second.facts.snapshot_id)
        self.assertEqual(first.decision_risk_supplier_id, "fast")
        self.assertEqual(len(first.baseline_outcome.purchase_options), 3)
        self.assertEqual(len(first.facts.simulations), 4)

    def test_valid_reasoning_creates_human_review_packet(self) -> None:
        workflow_input = make_input()
        result = run_decision_workflow(workflow_input, FakeReasoner(valid_proposal(workflow_input)))
        self.assertEqual(result.status, DecisionWorkflowStatus.READY_FOR_REVIEW)
        self.assertIsNotNone(result.review_packet)
        self.assertTrue(result.reference_validation.valid)
        self.assertTrue(result.policy_validation.compliant)
        self.assertTrue(result.policy_validation.requires_human_approval)

    def test_infeasible_options_are_evidence_but_not_eligible(self) -> None:
        result = run_decision_workflow(make_input())
        all_ids = {option.option_id for option in result.facts.purchase_options}
        eligible_ids = set(result.facts.eligible_scenario_ids)
        self.assertIn("late:product-1", all_ids)
        self.assertIn("expensive:product-1", all_ids)
        self.assertNotIn("PURCHASE_late:product-1", eligible_ids)
        self.assertNotIn("PURCHASE_expensive:product-1", eligible_ids)

    def test_invalid_reasoning_is_rejected_not_repaired(self) -> None:
        bad = LLMDecisionProposal(
            selected_scenario_id="PURCHASE_unknown",
            confidence=DecisionConfidence.HIGH,
        )
        result = run_decision_workflow(make_input(), FakeReasoner(bad))
        self.assertEqual(result.status, DecisionWorkflowStatus.REASONING_REJECTED)
        self.assertFalse(result.reference_validation.valid)
        self.assertIsNone(result.review_packet)

    def test_reasoner_error_keeps_evidence_usable(self) -> None:
        result = run_decision_workflow(make_input(), FakeReasoner(RuntimeError("network unavailable")))
        self.assertEqual(result.status, DecisionWorkflowStatus.REASONING_UNAVAILABLE)
        self.assertIsNone(result.proposal)
        self.assertTrue(result.facts.purchase_options)

    def test_policy_violation_requires_policy_review(self) -> None:
        workflow_input = make_input(allowed_actions=[])
        result = run_decision_workflow(workflow_input, FakeReasoner(valid_proposal(workflow_input)))
        self.assertEqual(result.status, DecisionWorkflowStatus.POLICY_REVIEW_REQUIRED)
        self.assertFalse(result.policy_validation.compliant)
        self.assertTrue(result.policy_validation.requires_human_approval)

    def test_what_if_uses_the_exact_immutable_evaluated_baseline(self) -> None:
        result = run_decision_workflow(make_input())
        scenario = WhatIfScenario(
            scenario_id="demand-up", name="Demand increase",
            shocks=(NumericShock(target=ShockTarget.DEMAND, mode=AdjustmentMode.PERCENTAGE, value=50),),
        )
        before, counterfactual = run_what_if(result.baseline, scenario)
        self.assertEqual(before, result.baseline_outcome)
        self.assertEqual(result.baseline.product.daily_demand, 6)
        self.assertEqual(counterfactual.derived_state.derived_product.daily_demand, 9)


if __name__ == "__main__":
    unittest.main()
