"""Persistence and audit tests for Milestone 8, using isolated SQLite files."""

import json
from pathlib import Path
import tempfile
import unittest

from core.decision_persistence import (
    get_decision_review,
    get_what_if_scenario,
    list_audit_events,
    list_decision_reviews,
    list_what_if_scenarios,
    save_decision_review,
    save_what_if_scenario,
)
from core.decision_workflow import run_decision_workflow
from core.what_if import run_what_if
from core.what_if_comparison import compare_business_outcomes
from database.database import Database
from core.config import get_admin_email
from models.business import Business
from models.decision_workflow import DecisionWorkflowInput
from models.inventory import Product
from models.persistence import AuditEventType
from models.policy import Policy
from models.supplier import Supplier, SupplierProduct
from models.what_if import AdjustmentMode, NumericShock, ShockTarget, WhatIfScenario
from models.user import User, UserRole


def workflow_input(*, current_stock: int = 12) -> DecisionWorkflowInput:
    business = Business(id="business-1", name="Demo", country="IN", currency="INR", industry="Retail", inventory_budget=5000)
    product = Product(
        id="product-1", business_id=business.id, sku="SKU-1", name="Milk",
        current_stock=current_stock, unit_cost=100, daily_demand=6, safety_stock=5,
    )
    policy = Policy(id="policy-1", business_id=business.id, require_approval=True)
    suppliers = (
        Supplier(id="fast", business_id=business.id, name="Fast", lead_time_days=1, reliability_score=.9),
        Supplier(id="late", business_id=business.id, name="Late", lead_time_days=5, reliability_score=.8),
    )
    terms = (
        SupplierProduct(supplier_id="fast", product_id=product.id, unit_price=120),
        SupplierProduct(supplier_id="late", product_id=product.id, unit_price=90),
    )
    return DecisionWorkflowInput(
        business=business, product=product, policy=policy, suppliers=suppliers,
        supplier_products=terms, available_budget=5000, simulation_days=7,
    )


class DecisionPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.tempdir.name) / "agentstock-test.db")
        self.database.initialize()
        self.admin_user = User(
            id="admin-test", name="Admin", email=get_admin_email(),
            password_hash="test", role=UserRole.ADMIN.value,
        )

    def tearDown(self) -> None:
        self.database.close()
        self.tempdir.cleanup()

    def test_create_retrieve_and_immutably_resave_decision_snapshot(self) -> None:
        result = run_decision_workflow(workflow_input())
        saved = save_decision_review(self.database, result)
        reopened = get_decision_review(self.database, saved.snapshot_id)
        again = save_decision_review(self.database, result)
        self.assertEqual(saved.facts, result.facts)
        self.assertEqual(reopened.facts, result.facts)
        self.assertEqual(again.created_at, saved.created_at)
        self.assertEqual(len(list_decision_reviews(self.database)), 1)
        created = [event for event in list_audit_events(self.database, self.admin_user) if event.event_type is AuditEventType.DECISION_CREATED]
        self.assertEqual(len(created), 1)

    def test_changed_input_creates_a_new_snapshot(self) -> None:
        first = save_decision_review(self.database, run_decision_workflow(workflow_input(current_stock=12)))
        second = save_decision_review(self.database, run_decision_workflow(workflow_input(current_stock=5)))
        self.assertNotEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(len(list_decision_reviews(self.database, business_id="business-1", product_id="product-1")), 2)
        self.assertEqual(get_decision_review(self.database, first.snapshot_id).facts.inventory_risk.current_stock, 12)

    def test_saved_what_if_reopens_without_mutating_its_baseline(self) -> None:
        result = run_decision_workflow(workflow_input())
        saved_decision = save_decision_review(self.database, result)
        scenario = WhatIfScenario(
            scenario_id="demand-up", name="Demand increase",
            shocks=(NumericShock(target=ShockTarget.DEMAND, mode=AdjustmentMode.PERCENTAGE, value=50),),
        )
        baseline, counterfactual = run_what_if(result.baseline, scenario)
        comparison = compare_business_outcomes(baseline, counterfactual)
        saved = save_what_if_scenario(self.database, saved_decision.snapshot_id, scenario, comparison)
        reopened = get_what_if_scenario(self.database, saved.id)
        self.assertEqual(reopened.comparison, comparison)
        self.assertEqual(reopened.decision_snapshot_id, saved_decision.snapshot_id)
        self.assertEqual(reopened.baseline_snapshot_id, result.baseline.baseline_snapshot_id)
        self.assertEqual(result.baseline.product.daily_demand, 6)
        self.assertEqual(len(list_what_if_scenarios(self.database, decision_snapshot_id=saved_decision.snapshot_id)), 1)
        event_types = [event.event_type for event in list_audit_events(self.database, self.admin_user)]
        self.assertIn(AuditEventType.WHAT_IF_CREATED, event_types)
        self.assertIn(AuditEventType.WHAT_IF_VIEWED, event_types)

    def test_audit_tracks_view_events_without_secrets(self) -> None:
        saved = save_decision_review(self.database, run_decision_workflow(workflow_input()))
        get_decision_review(self.database, saved.snapshot_id)
        all_rows = self.database.connect().execute(
            "SELECT facts_json, proposal_json, reference_validation_json, policy_validation_json FROM decision_snapshots"
        ).fetchall()
        persisted_json = "\n".join(" ".join(value or "" for value in row) for row in all_rows).lower()
        self.assertNotIn("api_key", persisted_json)
        self.assertNotIn("credential", persisted_json)
        events = list_audit_events(self.database, self.admin_user)
        self.assertIn(AuditEventType.DECISION_CREATED, [event.event_type for event in events])
        self.assertIn(AuditEventType.DECISION_VIEWED, [event.event_type for event in events])

    def test_corrupted_snapshot_is_rejected_safely(self) -> None:
        saved = save_decision_review(self.database, run_decision_workflow(workflow_input()))
        self.database.connect().execute(
            "UPDATE decision_snapshots SET facts_json = ? WHERE snapshot_id = ?", ("{not-json", saved.snapshot_id)
        )
        self.database.connect().commit()
        with self.assertRaisesRegex(ValueError, "corrupted"):
            get_decision_review(self.database, saved.snapshot_id)

    def test_invalid_what_if_baseline_is_rejected_without_audit(self) -> None:
        result = run_decision_workflow(workflow_input())
        scenario = WhatIfScenario(scenario_id="x", name="x", shocks=())
        baseline, counterfactual = run_what_if(result.baseline, scenario)
        with self.assertRaisesRegex(ValueError, "baseline snapshot was not found"):
            save_what_if_scenario(self.database, "0" * 64, scenario, compare_business_outcomes(baseline, counterfactual))
        self.assertEqual(list_audit_events(self.database, self.admin_user), [])


if __name__ == "__main__":
    unittest.main()
