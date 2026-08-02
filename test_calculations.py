"""Lightweight standard-library tests for the deterministic risk engine."""

import unittest

from core.calculations import analyze_inventory_risk, calculate_projected_inventory


class InventoryRiskCalculationTests(unittest.TestCase):
    def test_critical_shortfall(self) -> None:
        result = analyze_inventory_risk(12, 6, 5, 5)
        self.assertEqual(result.runway_days, 2)
        self.assertEqual(result.coverage_gap, -3)
        self.assertEqual(result.safety_stock_gap, 7)
        self.assertEqual(result.stockout_risk, "CRITICAL")
        self.assertEqual(result.reorder_requirement, 23)

    def test_low_risk_with_adequate_coverage(self) -> None:
        result = analyze_inventory_risk(100, 5, 10, 3)
        self.assertEqual(result.runway_days, 20)
        self.assertEqual(result.coverage_gap, 17)
        self.assertEqual(result.safety_stock_gap, 90)
        self.assertEqual(result.stockout_risk, "LOW")
        self.assertEqual(result.reorder_requirement, 0)

    def test_critical_low_inventory(self) -> None:
        result = analyze_inventory_risk(5, 10, 10, 5)
        self.assertEqual(result.runway_days, 0.5)
        self.assertEqual(result.stockout_risk, "CRITICAL")
        self.assertGreater(result.reorder_requirement, 0)

    def test_zero_demand_is_explicitly_undefined_runway(self) -> None:
        result = analyze_inventory_risk(0, 0, 5, 5)
        self.assertIsNone(result.runway_days)
        self.assertIsNone(result.coverage_gap)
        self.assertEqual(result.stockout_risk, "MEDIUM")
        self.assertEqual(result.reorder_requirement, 5)

    def test_negative_stock_fails(self) -> None:
        with self.assertRaises(ValueError):
            analyze_inventory_risk(-1, 1, 1, 1)

    def test_negative_demand_fails(self) -> None:
        with self.assertRaises(ValueError):
            analyze_inventory_risk(1, -1, 1, 1)

    def test_negative_lead_time_fails(self) -> None:
        with self.assertRaises(ValueError):
            analyze_inventory_risk(1, 1, 1, -1)

    def test_projection_preserves_shortage(self) -> None:
        self.assertEqual(calculate_projected_inventory(12, 6, 3), -6)


if __name__ == "__main__":
    unittest.main()
