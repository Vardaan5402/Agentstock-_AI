"""Standard-library tests for Milestone 5 decision intelligence boundaries."""

from datetime import datetime, timezone
import unittest

from core.calculations import analyze_inventory_risk
from core.constraints import build_purchase_option
from core.decision_context import (
    build_decision_facts,
    build_review_packet,
    derive_required_uncertainties,
    validate_proposal_references,
)
from core.gemini_reasoner import GeminiStructuredReasoner, request_structured_decision
from core.policy_validation import validate_decision_policy
from core.simulator import simulate_options
from models.business import Business
from models.decision_intelligence import (
    DecisionConfidence,
    LLMDecisionProposal,
    ReasoningClaim,
    ReasoningConclusion,
    ReasoningDimension,
    UncertaintyCode,
)
from models.inventory import Product
from models.policy import Policy
from models.supplier import Supplier, SupplierProduct


FIXED_TIME = datetime(2026, 8, 1, tzinfo=timezone.utc)


def make_inputs(
    *, daily_demand: float = 6, policy_limit: float = 5000,
    allowed_actions: list[str] | None = None, require_approval: bool = True,
    include_feasible: bool = True,
):
    business = Business(
        id="business-1", name="Demo", country="IN", currency="INR", industry="Retail",
        inventory_budget=5000,
    )
    policy = Policy(
        id="policy-1", business_id=business.id, max_auto_purchase=policy_limit,
        require_approval=require_approval,
        allowed_auto_actions=["PURCHASE"] if allowed_actions is None else allowed_actions,
    )
    product = Product(
        id="product-1", business_id=business.id, sku="SKU-1", name="Milk",
        current_stock=12, unit_cost=100, daily_demand=daily_demand, safety_stock=5,
    )
    feasible_supplier = Supplier(
        id="supplier-feasible", business_id=business.id, name="Feasible", lead_time_days=1,
        reliability_score=0.9,
    )
    infeasible_supplier = Supplier(
        id="supplier-infeasible", business_id=business.id, name="Infeasible", lead_time_days=5,
        reliability_score=0.8,
    )
    options = []
    if include_feasible:
        options.append(build_purchase_option(
            feasible_supplier,
            SupplierProduct(supplier_id=feasible_supplier.id, product_id=product.id, unit_price=120),
            product,
            5000,
            23,
        ))
    options.append(build_purchase_option(
        infeasible_supplier,
        SupplierProduct(
            supplier_id=infeasible_supplier.id, product_id=product.id,
            unit_price=200, minimum_order_quantity=50,
        ),
        product,
        5000,
        23,
    ))
    simulations = simulate_options(product.current_stock, product.daily_demand, 7, options)
    risk = analyze_inventory_risk(
        product.current_stock, product.daily_demand, product.safety_stock, 1
    )
    facts = build_decision_facts(
        business, policy, product.id, risk, options, simulations, created_at=FIXED_TIME
    )
    return business, policy, product, options, simulations, facts


def proposal(selected_scenario_id: str, *, claims=(), uncertainties=()):
    return LLMDecisionProposal(
        selected_scenario_id=selected_scenario_id,
        reasoning_claims=claims,
        confidence=DecisionConfidence.MEDIUM,
        uncertainty_codes=uncertainties,
    )


class FakeReasoner:
    def __init__(self, response: LLMDecisionProposal) -> None:
        self.response = response

    def propose(self, facts):
        return self.response


class DecisionIntelligenceTests(unittest.TestCase):
    def test_valid_facts_and_deterministic_snapshot_id(self) -> None:
        *_, first = make_inputs()
        *_, second = make_inputs()
        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(first.eligible_scenario_ids[0], "DO_NOTHING")
        business, policy, product, options, simulations, _ = make_inputs()
        later = build_decision_facts(
            business, policy, product.id, analyze_inventory_risk(12, 6, 5, 1),
            options, simulations, created_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
        )
        self.assertEqual(first.snapshot_id, later.snapshot_id)

    def test_eligibility_preserves_infeasible_simulations(self) -> None:
        *_, options, simulations, facts = make_inputs()
        feasible_id = f"PURCHASE_{options[0].option_id}"
        infeasible_id = f"PURCHASE_{options[1].option_id}"
        self.assertIn(feasible_id, facts.eligible_scenario_ids)
        self.assertNotIn(infeasible_id, facts.eligible_scenario_ids)
        self.assertIn(infeasible_id, [item.scenario_id for item in facts.simulations])
        self.assertEqual(len(simulations), len(facts.simulations))

    def test_invalid_product_and_scenario_linkage_fail(self) -> None:
        business, policy, product, options, simulations, _ = make_inputs()
        wrong_product_option = options[0].model_copy(update={"product_id": "wrong-product"})
        with self.assertRaises(ValueError):
            build_decision_facts(
                business, policy, product.id, analyze_inventory_risk(12, 6, 5, 1),
                [wrong_product_option, options[1]], simulations, created_at=FIXED_TIME,
            )
        mismatched_simulation = simulations[1].model_copy(update={"supplier_id": "wrong-supplier"})
        with self.assertRaises(ValueError):
            build_decision_facts(
                business, policy, product.id, analyze_inventory_risk(12, 6, 5, 1),
                options, [simulations[0], mismatched_simulation, *simulations[2:]],
                created_at=FIXED_TIME,
            )

    def test_invalid_selected_scenario_is_rejected(self) -> None:
        *_, options, _, facts = make_inputs()
        result = validate_proposal_references(facts, proposal(f"PURCHASE_{options[1].option_id}"))
        self.assertFalse(result.valid)
        self.assertIn("selected_scenario_id is not eligible", result.errors)

    def test_fabricated_unknown_and_valid_fact_references(self) -> None:
        *_, options, _, facts = make_inputs()
        selected = f"PURCHASE_{options[0].option_id}"
        fabricated = ReasoningClaim(
            dimension=ReasoningDimension.COST, conclusion=ReasoningConclusion.TRADEOFF,
            fact_references=("/simulations/UNKNOWN/price",),
        )
        unknown_scenario = ReasoningClaim(
            dimension=ReasoningDimension.RELIABILITY, conclusion=ReasoningConclusion.RISK_FLAG,
            compared_scenario_ids=("UNKNOWN",),
        )
        invalid = validate_proposal_references(
            facts, proposal(selected, claims=(fabricated, unknown_scenario))
        )
        self.assertFalse(invalid.valid)
        self.assertEqual(len(invalid.errors), 2)
        valid_claim = ReasoningClaim(
            dimension=ReasoningDimension.COST, conclusion=ReasoningConclusion.FAVORS_SELECTED,
            compared_scenario_ids=("DO_NOTHING", selected),
            fact_references=(
                f"/purchase_options/{options[0].option_id}/total_cost",
                f"/simulations/{selected}/ending_inventory",
            ),
        )
        valid = validate_proposal_references(facts, proposal(selected, claims=(valid_claim,)))
        self.assertTrue(valid.valid)
        policy_result = validate_decision_policy(facts, proposal(selected, claims=(valid_claim,)))
        packet = build_review_packet(facts, proposal(selected, claims=(valid_claim,)), valid, policy_result)
        self.assertEqual(packet.facts.snapshot_id, facts.snapshot_id)
        self.assertEqual(packet.proposal.selected_scenario_id, selected)

    def test_policy_approval_requirement_limit_and_disallowed_action(self) -> None:
        *_, options, _, facts = make_inputs()
        selected = f"PURCHASE_{options[0].option_id}"
        approval = validate_decision_policy(facts, proposal(selected))
        self.assertTrue(approval.compliant)
        self.assertTrue(approval.requires_human_approval)
        *_, _, _, limited_facts = make_inputs(policy_limit=100, require_approval=False)
        limit = validate_decision_policy(limited_facts, proposal(selected))
        self.assertFalse(limit.compliant)
        self.assertTrue(limit.requires_human_approval)
        self.assertIn("AUTO_PURCHASE_LIMIT_EXCEEDED", limit.violations)
        *_, _, _, disallowed_facts = make_inputs(allowed_actions=[], require_approval=False)
        disallowed = validate_decision_policy(disallowed_facts, proposal(selected))
        self.assertFalse(disallowed.compliant)
        self.assertIn("ACTION_NOT_ALLOWED", disallowed.violations)

    def test_zero_demand_and_no_feasible_option_uncertainties(self) -> None:
        *_, _, _, zero_facts = make_inputs(daily_demand=0, include_feasible=False)
        required = derive_required_uncertainties(zero_facts, "DO_NOTHING")
        self.assertIn(UncertaintyCode.ZERO_DEMAND_FORECAST, required)
        self.assertIn(UncertaintyCode.NO_FEASIBLE_PURCHASE_OPTION, required)
        checked = validate_proposal_references(
            zero_facts,
            proposal("DO_NOTHING", uncertainties=tuple(required)),
        )
        self.assertTrue(checked.valid)

    def test_late_arrival_uncertainty_and_reproducibility(self) -> None:
        *_, options, _, facts = make_inputs()
        late_scenario = f"PURCHASE_{options[1].option_id}"
        required = derive_required_uncertainties(facts, late_scenario)
        self.assertIn(UncertaintyCode.LATE_ARRIVAL_STOCKOUT, required)
        self.assertEqual(facts.canonical_json(), facts.canonical_json())

    def test_fake_reasoner_and_real_adapter_import_without_network(self) -> None:
        *_, options, _, facts = make_inputs()
        selected = f"PURCHASE_{options[0].option_id}"
        expected = proposal(selected)
        self.assertEqual(request_structured_decision(facts, FakeReasoner(expected)), expected)
        self.assertTrue(callable(GeminiStructuredReasoner))


if __name__ == "__main__":
    unittest.main()
