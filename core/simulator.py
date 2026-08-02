"""Deterministic counterfactual inventory simulation for AgentStock."""

from enum import Enum
from math import ceil, isfinite
from numbers import Integral, Real
from typing import Iterable

from pydantic import BaseModel, Field

from core.constraints import PurchaseOption


class SimulationActionType(str, Enum):
    """The supported counterfactual inventory actions."""

    DO_NOTHING = "DO_NOTHING"
    PURCHASE = "PURCHASE"


class SimulationAction(BaseModel):
    """A possible inventory action to simulate, without recommending it."""

    action_type: SimulationActionType
    supplier_id: str | None = None
    quantity: float = Field(default=0.0, ge=0)
    unit_price: float = Field(default=0.0, ge=0)
    purchase_cost: float = Field(default=0.0, ge=0)
    lead_time_days: float = Field(default=0.0, ge=0)


class InventoryPoint(BaseModel):
    """The explainable state transition for one simulated demand day."""

    day: int = Field(ge=0)
    starting_inventory: float
    demand: float = Field(ge=0)
    incoming_quantity: float = Field(ge=0)
    ending_inventory: float


class SimulationResult(BaseModel):
    """The deterministic consequences of one action over a fixed horizon."""

    scenario_id: str = Field(min_length=1)
    action_type: SimulationActionType
    supplier_id: str | None = None
    purchase_quantity: float = Field(ge=0)
    purchase_cost: float = Field(ge=0)
    lead_time_days: float = Field(ge=0)
    arrival_day: int | None = Field(default=None, ge=0)
    stockout_day: int | None = Field(default=None, ge=0)
    minimum_inventory: float
    ending_inventory: float
    total_shortage_units: float = Field(ge=0)
    inventory_trajectory: list[InventoryPoint]


def simulate_inventory(
    current_stock: Real, daily_demand: Real, days: Integral
) -> list[float]:
    """Return inventory at day zero and after every simulated demand day."""
    stock = _validate_non_negative_number("current_stock", current_stock)
    demand = _validate_non_negative_number("daily_demand", daily_demand)
    horizon = _validate_day_count("days", days)
    return [stock - (demand * day) for day in range(horizon + 1)]


def calculate_stockout_day(
    current_stock: Real, daily_demand: Real
) -> int | None:
    """Return elapsed whole day when stock reaches zero or below without purchases.

    Day 0 denotes inventory already at zero. ``None`` denotes no demand-driven
    stockout because daily demand is zero.
    """
    stock = _validate_non_negative_number("current_stock", current_stock)
    demand = _validate_non_negative_number("daily_demand", daily_demand)
    if demand == 0:
        return None
    if stock == 0:
        return 0
    return ceil(stock / demand)


def simulate_action(
    current_stock: Real,
    daily_demand: Real,
    simulation_days: Integral,
    action: SimulationAction,
    scenario_id: str,
) -> SimulationResult:
    """Simulate one action using start-of-day arrivals before demand.

    A fractional lead time is scheduled on the next whole daily boundary using
    ``ceil(lead_time_days)``. Total shortage is cumulative negative ending
    inventory across all simulated days, measuring unmet-demand exposure.
    """
    stock = _validate_non_negative_number("current_stock", current_stock)
    demand = _validate_non_negative_number("daily_demand", daily_demand)
    horizon = _validate_day_count("simulation_days", simulation_days)

    if action.action_type is SimulationActionType.DO_NOTHING:
        quantity = 0.0
        cost = 0.0
        lead_time = 0.0
        arrival_day = None
        supplier_id = None
    else:
        quantity = _validate_non_negative_number("action.quantity", action.quantity)
        cost = _validate_non_negative_number("action.purchase_cost", action.purchase_cost)
        lead_time = _validate_non_negative_number("action.lead_time_days", action.lead_time_days)
        arrival_day = ceil(lead_time) if quantity > 0 else None
        supplier_id = action.supplier_id

    trajectory: list[InventoryPoint] = []
    inventory = stock
    minimum_inventory = stock
    total_shortage = 0.0
    stockout_day: int | None = None

    if stock == 0 and demand > 0 and arrival_day != 0:
        stockout_day = 0

    for day in range(horizon):
        incoming = quantity if arrival_day == day else 0.0
        starting_inventory = inventory
        ending_inventory = starting_inventory + incoming - demand
        trajectory.append(
            InventoryPoint(
                day=day,
                starting_inventory=starting_inventory,
                demand=demand,
                incoming_quantity=incoming,
                ending_inventory=ending_inventory,
            )
        )
        minimum_inventory = min(minimum_inventory, ending_inventory)
        if ending_inventory < 0:
            total_shortage += abs(ending_inventory)
        if stockout_day is None and ending_inventory <= 0:
            stockout_day = day + 1
        inventory = ending_inventory

    return SimulationResult(
        scenario_id=scenario_id,
        action_type=action.action_type,
        supplier_id=supplier_id,
        purchase_quantity=quantity,
        purchase_cost=cost,
        lead_time_days=lead_time,
        arrival_day=arrival_day,
        stockout_day=stockout_day,
        minimum_inventory=minimum_inventory,
        ending_inventory=inventory,
        total_shortage_units=total_shortage,
        inventory_trajectory=trajectory,
    )


def simulate_options(
    current_stock: Real,
    daily_demand: Real,
    simulation_days: Integral,
    purchase_options: Iterable[PurchaseOption],
) -> list[SimulationResult]:
    """Simulate DO_NOTHING followed by each supplied option in input order.

    Options are neither filtered by feasibility nor sorted: this is a
    consequence simulator, so it shows the outcome of every supplied action.
    """
    do_nothing = SimulationAction(action_type=SimulationActionType.DO_NOTHING)
    results = [
        simulate_action(
            current_stock,
            daily_demand,
            simulation_days,
            do_nothing,
            scenario_id="DO_NOTHING",
        )
    ]
    for option in purchase_options:
        action = SimulationAction(
            action_type=SimulationActionType.PURCHASE,
            supplier_id=option.supplier_id,
            quantity=option.purchase_quantity,
            unit_price=option.unit_price,
            purchase_cost=option.total_cost,
            lead_time_days=option.supplier_lead_time_days,
        )
        results.append(
            simulate_action(
                current_stock,
                daily_demand,
                simulation_days,
                action,
                scenario_id=f"PURCHASE_{option.option_id}",
            )
        )
    return results


def _validate_day_count(name: str, value: Integral) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be a whole number")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return int(value)


def _validate_non_negative_number(name: str, value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    if number < 0:
        raise ValueError(f"{name} must be non-negative")
    return number
