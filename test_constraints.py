"""Standard-library tests for deterministic supplier and cash constraints."""

import unittest

from core.constraints import (
    ReasonCode,
    build_purchase_option,
    calculate_purchase_cost,
    calculate_purchase_quantity,
    check_budget_feasibility,
    check_lead_time_feasibility,
    evaluate_supplier_options,
)
from models.inventory import Product
from models.supplier import Supplier, SupplierProduct


def product() -> Product:
    return Product(
        id="product-1", business_id="business-1", sku="SKU-1", name="Milk",
        current_stock=12, unit_cost=100, daily_demand=6, safety_stock=5,
    )


def supplier(
    supplier_id: str = "supplier-1", lead_time: float = 1, reliability: float = 0.9
) -> Supplier:
    return Supplier(
        id=supplier_id, business_id="business-1", name=supplier_id,
        lead_time_days=lead_time, reliability_score=reliability,
    )


def terms(supplier_id: str = "supplier-1", price: float = 120, moq: int = 10) -> SupplierProduct:
    return SupplierProduct(
        supplier_id=supplier_id, product_id="product-1", unit_price=price,
        minimum_order_quantity=moq,
    )


class SupplierConstraintTests(unittest.TestCase):
    def test_normal_feasible_supplier(self) -> None:
        option = build_purchase_option(supplier(), terms(), product(), 5000, 23)
        self.assertEqual(option.purchase_quantity, 23)
        self.assertEqual(option.total_cost, 2760)
        self.assertTrue(option.financially_feasible)
        self.assertTrue(option.operationally_feasible)
        self.assertTrue(option.feasible)

    def test_moq_increases_purchase_quantity(self) -> None:
        self.assertEqual(calculate_purchase_quantity(23, 50), 50)

    def test_moq_can_cause_budget_failure(self) -> None:
        option = build_purchase_option(supplier(), terms(price=110, moq=50), product(), 5000, 23)
        self.assertEqual(option.purchase_quantity, 50)
        self.assertEqual(option.total_cost, 5500)
        self.assertFalse(option.financially_feasible)
        self.assertFalse(option.feasible)
        self.assertEqual(option.reason_code, ReasonCode.INSUFFICIENT_BUDGET)

    def test_lead_time_can_exceed_runway(self) -> None:
        option = build_purchase_option(supplier(lead_time=5), terms(), product(), 5000, 23)
        self.assertFalse(option.operationally_feasible)
        self.assertEqual(option.coverage_gap, -3)
        self.assertFalse(option.feasible)
        self.assertEqual(option.reason_code, ReasonCode.SUPPLIER_LEAD_TIME_EXCEEDS_RUNWAY)

    def test_both_constraints_can_fail(self) -> None:
        option = build_purchase_option(supplier(lead_time=5), terms(price=200, moq=50), product(), 5000, 23)
        self.assertFalse(option.financially_feasible)
        self.assertFalse(option.operationally_feasible)
        self.assertFalse(option.feasible)
        self.assertEqual(option.reason_code, ReasonCode.MULTIPLE_CONSTRAINT_FAILURES)

    def test_zero_required_quantity_does_not_force_moq(self) -> None:
        option = build_purchase_option(supplier(), terms(moq=50), product(), 5000, 0)
        self.assertEqual(option.purchase_quantity, 0)
        self.assertEqual(option.total_cost, 0)
        self.assertEqual(option.reason_code, ReasonCode.ZERO_REQUIRED_QUANTITY)

    def test_multiple_suppliers_are_all_evaluated_without_ranking(self) -> None:
        suppliers = [supplier("supplier-1"), supplier("supplier-2"), supplier("supplier-3")]
        supplier_products = [
            terms("supplier-1", price=120),
            terms("supplier-2", price=130),
            terms("supplier-3", price=140),
            SupplierProduct(supplier_id="supplier-1", product_id="other-product", unit_price=1),
        ]
        options = evaluate_supplier_options(product(), suppliers, supplier_products, 5000, 23)
        self.assertEqual([option.supplier_id for option in options], ["supplier-1", "supplier-2", "supplier-3"])
        self.assertFalse(any(hasattr(option, "recommendation_score") for option in options))

    def test_invalid_numeric_inputs_raise_errors(self) -> None:
        with self.assertRaises(ValueError):
            calculate_purchase_quantity(-1, 10)
        with self.assertRaises(ValueError):
            calculate_purchase_quantity(1, -1)
        with self.assertRaises(ValueError):
            calculate_purchase_cost(1, -1)
        with self.assertRaises(ValueError):
            check_budget_feasibility(1, -1)
        with self.assertRaises(ValueError):
            check_lead_time_feasibility(1, -1)
        with self.assertRaises(ValueError):
            build_purchase_option(supplier(), terms(price=10), product(), -1, 1)
        with self.assertRaises(ValueError):
            Product(
                id="bad-product", business_id="business-1", sku="BAD", name="Bad",
                current_stock=-1, unit_cost=1, daily_demand=1,
            )
        with self.assertRaises(ValueError):
            Supplier(
                id="bad-supplier", business_id="business-1", name="Bad",
                lead_time_days=1, reliability_score=-0.1,
            )


if __name__ == "__main__":
    unittest.main()
