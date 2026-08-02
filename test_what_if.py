import unittest
from models.business import Business
from models.inventory import Product
from models.supplier import Supplier, SupplierProduct
from models.what_if import AdjustmentMode, NumericShock, ShockTarget, WhatIfScenario
from core.what_if import (
    apply_numeric_shock,
    build_business_scenario_baseline,
    derive_counterfactual_state,
    evaluate_baseline,
    evaluate_business_state,
    run_what_if,
)
from core.what_if_comparison import compare_business_outcomes
from core.gemini_what_if_explainer import validate_explanation_references
from models.what_if import WhatIfExplanation, WhatIfExplanationClaim
from models.decision_intelligence import DecisionConfidence, ReasoningConclusion, ReasoningDimension


class WhatIfTests(unittest.TestCase):
    def setUp(self):
        self.business = Business(id="b1", name="Shop", country="IN", currency="INR", industry="retail", inventory_budget=500)
        self.product = Product(id="p1", business_id="b1", sku="SKU1", name="Widget", current_stock=20, unit_cost=10, daily_demand=5, safety_stock=5)
        self.suppliers = (
            Supplier(id="s1", business_id="b1", name="A", lead_time_days=2, reliability_score=.9),
            Supplier(id="s2", business_id="b1", name="B", lead_time_days=5, reliability_score=.8),
        )
        self.terms = (
            SupplierProduct(supplier_id="s1", product_id="p1", unit_price=10, minimum_order_quantity=1, feasible=True),
            SupplierProduct(supplier_id="s2", product_id="p1", unit_price=12, minimum_order_quantity=2, feasible=True),
        )
        self.baseline = build_business_scenario_baseline(self.business, self.product, self.suppliers, self.terms, 500, 7)

    def test_snapshot_deterministic_and_baseline_immutable(self):
        again = build_business_scenario_baseline(self.business, self.product, self.suppliers, self.terms, 500, 7)
        self.assertEqual(self.baseline.baseline_snapshot_id, again.baseline_snapshot_id)
        scenario = WhatIfScenario(scenario_id="demand-up", name="Demand", shocks=(NumericShock(target=ShockTarget.DEMAND, mode=AdjustmentMode.PERCENTAGE, value=100),))
        state = derive_counterfactual_state(self.baseline, scenario)
        self.assertEqual(self.baseline.product.daily_demand, 5)
        self.assertEqual(state.derived_product.daily_demand, 10)

    def test_apply_shocks_and_risk_change(self):
        scenario = WhatIfScenario(scenario_id="demand-up", name="Demand", shocks=(NumericShock(target=ShockTarget.DEMAND, mode=AdjustmentMode.PERCENTAGE, value=100),))
        base, counter = run_what_if(self.baseline, scenario)
        self.assertLess(counter.supplier_outcomes[0].inventory_risk.runway_days, base.supplier_outcomes[0].inventory_risk.runway_days)
        self.assertEqual(counter.supplier_outcomes[0].inventory_risk.stockout_risk, "CRITICAL")

    def test_price_budget_and_moq_shocks(self):
        scenario = WhatIfScenario(scenario_id="commercial", name="Commercial", shocks=(
            NumericShock(target=ShockTarget.SUPPLIER_PRICE, mode=AdjustmentMode.PERCENTAGE, value=50, supplier_id="s1"),
            NumericShock(target=ShockTarget.MOQ, mode=AdjustmentMode.SET, value=20, supplier_id="s1"),
            NumericShock(target=ShockTarget.AVAILABLE_BUDGET, mode=AdjustmentMode.SET, value=100, supplier_id=None),
            NumericShock(target=ShockTarget.INVENTORY, mode=AdjustmentMode.SET, value=0, supplier_id=None),
        ))
        state = derive_counterfactual_state(self.baseline, scenario)
        self.assertEqual(state.derived_supplier_products[0].unit_price, 15)
        self.assertEqual(state.derived_supplier_products[0].minimum_order_quantity, 20)
        self.assertEqual(state.derived_available_budget, 100)
        outcome = evaluate_business_state(self.baseline, state)
        self.assertFalse(outcome.purchase_options[0].financially_feasible)

    def test_lead_time_and_reliability(self):
        scenario = WhatIfScenario(scenario_id="supplier", name="Supplier", shocks=(
            NumericShock(target=ShockTarget.SUPPLIER_LEAD_TIME, mode=AdjustmentMode.DELTA, value=3, supplier_id="s1"),
            NumericShock(target=ShockTarget.SUPPLIER_RELIABILITY, mode=AdjustmentMode.SET, value=.4, supplier_id="s1"),
        ))
        state = derive_counterfactual_state(self.baseline, scenario)
        self.assertEqual(state.derived_suppliers[0].lead_time_days, 5)
        self.assertEqual(state.derived_suppliers[0].reliability_score, .4)

    def test_invalid_targets_and_negative_results(self):
        with self.assertRaises(ValueError):
            derive_counterfactual_state(self.baseline, WhatIfScenario(scenario_id="x", name="x", shocks=(NumericShock(target=ShockTarget.SUPPLIER_PRICE, mode=AdjustmentMode.SET, value=1, supplier_id="missing"),)))
        with self.assertRaises(ValueError):
            apply_numeric_shock(10, NumericShock(target=ShockTarget.DEMAND, mode=AdjustmentMode.DELTA, value=-20))
        with self.assertRaises(ValueError):
            derive_counterfactual_state(self.baseline, WhatIfScenario(scenario_id="x", name="x", shocks=(NumericShock(target=ShockTarget.MOQ, mode=AdjustmentMode.SET, value=1.5, supplier_id="s1"),)))

    def test_comparison_preserves_supplier_identity(self):
        base, counter = run_what_if(self.baseline, WhatIfScenario(scenario_id="x", name="x", shocks=(NumericShock(target=ShockTarget.DEMAND, mode=AdjustmentMode.DELTA, value=1),)))
        comparison = compare_business_outcomes(base, counter)
        self.assertEqual([x.supplier_id for x in comparison.supplier_comparisons], ["s1", "s2"])
        self.assertEqual(comparison.supplier_comparisons[0].runway_days.baseline_value, 4)

    def test_explanation_reference_validation(self):
        base, counter = run_what_if(self.baseline, WhatIfScenario(scenario_id="x", name="x", shocks=()))
        comparison = compare_business_outcomes(base, counter)
        good = WhatIfExplanation(scenario_id="x", confidence=DecisionConfidence.HIGH, explanation_claims=(WhatIfExplanationClaim(dimension=ReasoningDimension.COST, conclusion=ReasoningConclusion.TRADEOFF, fact_references=("/supplier_comparisons/0/purchase_cost",)),))
        bad = WhatIfExplanation(scenario_id="x", confidence=DecisionConfidence.HIGH, explanation_claims=(WhatIfExplanationClaim(dimension=ReasoningDimension.COST, conclusion=ReasoningConclusion.TRADEOFF, fact_references=("/invented/value",)),))
        self.assertEqual(validate_explanation_references(comparison, good)[0], True)
        self.assertEqual(validate_explanation_references(comparison, bad)[0], False)


if __name__ == "__main__":
    unittest.main()
