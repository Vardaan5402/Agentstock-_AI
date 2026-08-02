"""Standard-library tests for AgentStock's deterministic simulator."""

import unittest

from core.constraints import PurchaseOption, ReasonCode
from core.simulator import (
    SimulationAction,
    SimulationActionType,
    calculate_stockout_day,
    simulate_action,
    simulate_inventory,
    simulate_options,
)


def purchase_option(
    option_id: str, supplier_id: str, quantity: int, lead_time: float
) -> PurchaseOption:
    return PurchaseOption(
        option_id=option_id,
        supplier_id=supplier_id,
        product_id="product-1",
        required_quantity=quantity,
        purchase_quantity=quantity,
        unit_price=10,
        total_cost=quantity * 10,
        available_budget=5000,
        budget_remaining=5000 - (quantity * 10),
        supplier_lead_time_days=lead_time,
        inventory_runway_days=2,
        coverage_gap=2 - lead_time,
        supplier_reliability=0.9,
        financially_feasible=True,
        operationally_feasible=True,
        feasible=True,
        reason_code=ReasonCode.FEASIBLE,
    )


class CounterfactualSimulatorTests(unittest.TestCase):
    def test_do_nothing(self) -> None:
        result = simulate_action(
            12, 6, 5, SimulationAction(action_type=SimulationActionType.DO_NOTHING), "DO_NOTHING"
        )
        self.assertEqual(result.stockout_day, 2)
        self.assertEqual(result.ending_inventory, -18)
        self.assertEqual(result.total_shortage_units, 36)
        self.assertEqual(simulate_inventory(12, 6, 5), [12, 6, 0, -6, -12, -18])

    def test_purchase_arrives_before_stockout(self) -> None:
        action = SimulationAction(
            action_type=SimulationActionType.PURCHASE,
            supplier_id="supplier-1",
            quantity=23,
            unit_price=10,
            purchase_cost=230,
            lead_time_days=1,
        )
        result = simulate_action(12, 6, 4, action, "PURCHASE_supplier-1")
        self.assertEqual(result.arrival_day, 1)
        self.assertEqual(result.inventory_trajectory[1].starting_inventory, 6)
        self.assertEqual(result.inventory_trajectory[1].incoming_quantity, 23)
        self.assertEqual(result.inventory_trajectory[1].ending_inventory, 23)
        self.assertIsNone(result.stockout_day)

    def test_purchase_arrives_after_stockout(self) -> None:
        action = SimulationAction(
            action_type=SimulationActionType.PURCHASE,
            supplier_id="supplier-1",
            quantity=23,
            purchase_cost=230,
            lead_time_days=5,
        )
        result = simulate_action(12, 6, 6, action, "PURCHASE_supplier-1")
        self.assertEqual(result.stockout_day, 2)
        self.assertEqual(result.inventory_trajectory[2].ending_inventory, -6)
        self.assertEqual(result.inventory_trajectory[5].incoming_quantity, 23)
        self.assertEqual(result.inventory_trajectory[5].ending_inventory, -1)

    def test_zero_demand_has_no_stockout(self) -> None:
        self.assertIsNone(calculate_stockout_day(100, 0))
        result = simulate_action(
            100, 0, 4, SimulationAction(action_type=SimulationActionType.DO_NOTHING), "DO_NOTHING"
        )
        self.assertIsNone(result.stockout_day)

    def test_zero_inventory_is_an_immediate_stockout(self) -> None:
        self.assertEqual(calculate_stockout_day(0, 3), 0)
        result = simulate_action(
            0, 3, 2, SimulationAction(action_type=SimulationActionType.DO_NOTHING), "DO_NOTHING"
        )
        self.assertEqual(result.stockout_day, 0)

    def test_multiple_supplier_scenarios_preserve_input_order(self) -> None:
        options = [
            purchase_option("supplier-1:product-1", "supplier-1", 20, 1),
            purchase_option("supplier-2:product-1", "supplier-2", 30, 2),
        ]
        results = simulate_options(12, 6, 4, options)
        self.assertEqual(
            [result.scenario_id for result in results],
            ["DO_NOTHING", "PURCHASE_supplier-1:product-1", "PURCHASE_supplier-2:product-1"],
        )
        self.assertFalse(any(hasattr(result, "recommendation_score") for result in results))

    def test_negative_inputs_fail(self) -> None:
        with self.assertRaises(ValueError):
            simulate_inventory(-1, 1, 1)
        with self.assertRaises(ValueError):
            simulate_inventory(1, -1, 1)
        with self.assertRaises(ValueError):
            simulate_inventory(1, 1, -1)

    def test_simulation_is_deterministic(self) -> None:
        action = SimulationAction(
            action_type=SimulationActionType.PURCHASE,
            supplier_id="supplier-1", quantity=23, purchase_cost=230, lead_time_days=1,
        )
        first = simulate_action(12, 6, 5, action, "PURCHASE_supplier-1")
        second = simulate_action(12, 6, 5, action, "PURCHASE_supplier-1")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
