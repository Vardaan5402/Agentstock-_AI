"""Deterministic inventory and stockout-risk calculations for AgentStock."""

from math import isfinite
from numbers import Real
from typing import Literal

from pydantic import BaseModel

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

CRITICAL_RUNWAY_DAYS = 2.0
HIGH_RUNWAY_DAYS = 4.0
MEDIUM_RUNWAY_DAYS = 7.0


class InventoryRiskResult(BaseModel):
    """The deterministic outcome of an inventory-risk assessment."""

    current_stock: float
    daily_demand: float
    safety_stock: float
    supplier_lead_time_days: float
    runway_days: float | None
    safety_stock_gap: float
    coverage_gap: float | None
    stockout_risk: RiskLevel
    reorder_requirement: float


def calculate_runway(current_stock: Real, daily_demand: Real) -> float | None:
    """Return days of inventory remaining, or ``None`` when demand is zero."""
    stock = _validate_non_negative("current_stock", current_stock)
    demand = _validate_non_negative("daily_demand", daily_demand)
    if demand == 0:
        return None
    return stock / demand


def calculate_safety_stock_gap(current_stock: Real, safety_stock: Real) -> float:
    """Return inventory above (positive) or below (negative) safety stock."""
    stock = _validate_non_negative("current_stock", current_stock)
    safety = _validate_non_negative("safety_stock", safety_stock)
    return stock - safety


def calculate_coverage_gap(
    runway_days: float | None, supplier_lead_time_days: Real
) -> float | None:
    """Return runway less lead time, or ``None`` if runway is undefined."""
    lead_time = _validate_non_negative("supplier_lead_time_days", supplier_lead_time_days)
    if runway_days is None:
        return None
    runway = _validate_non_negative("runway_days", runway_days)
    return runway - lead_time


def calculate_stockout_risk(
    runway_days: float | None,
    supplier_lead_time_days: Real | None,
    safety_stock_gap: Real,
) -> RiskLevel:
    """Classify stockout severity with explicit, ordered business rules.

    The first matching rule is the highest applicable severity. A ``None``
    runway denotes zero demand: there is no demand-driven stockout forecast, so
    the result is LOW unless inventory is already below safety stock (MEDIUM).
    """
    safety_gap = _validate_finite_number("safety_stock_gap", safety_stock_gap)
    lead_time = (
        None
        if supplier_lead_time_days is None
        else _validate_non_negative("supplier_lead_time_days", supplier_lead_time_days)
    )

    if runway_days is None:
        return "MEDIUM" if safety_gap < 0 else "LOW"

    runway = _validate_non_negative("runway_days", runway_days)

    if runway <= CRITICAL_RUNWAY_DAYS:
        return "CRITICAL"
    if lead_time is not None and runway < lead_time and runway <= 3:
        return "CRITICAL"
    if safety_gap < 0 and runway <= CRITICAL_RUNWAY_DAYS:
        return "CRITICAL"

    if runway <= HIGH_RUNWAY_DAYS:
        return "HIGH"
    if lead_time is not None and runway < lead_time:
        return "HIGH"

    if runway <= MEDIUM_RUNWAY_DAYS:
        return "MEDIUM"
    if safety_gap < 0:
        return "MEDIUM"
    return "LOW"


def calculate_reorder_requirement(
    current_stock: Real,
    daily_demand: Real,
    safety_stock: Real,
    supplier_lead_time_days: Real,
) -> float:
    """Return the stock shortfall needed to cover lead-time demand plus safety stock."""
    stock = _validate_non_negative("current_stock", current_stock)
    demand = _validate_non_negative("daily_demand", daily_demand)
    safety = _validate_non_negative("safety_stock", safety_stock)
    lead_time = _validate_non_negative("supplier_lead_time_days", supplier_lead_time_days)

    lead_time_demand = demand * lead_time
    target_stock = lead_time_demand + safety
    return max(0.0, target_stock - stock)


def calculate_projected_inventory(
    current_stock: Real, daily_demand: Real, days: Real
) -> float:
    """Return projected stock after demand over ``days``; shortages remain negative."""
    stock = _validate_non_negative("current_stock", current_stock)
    demand = _validate_non_negative("daily_demand", daily_demand)
    duration = _validate_non_negative("days", days)
    return stock - (demand * duration)


def analyze_inventory_risk(
    current_stock: Real,
    daily_demand: Real,
    safety_stock: Real,
    supplier_lead_time_days: Real,
) -> InventoryRiskResult:
    """Run the complete deterministic inventory-risk assessment."""
    stock = _validate_non_negative("current_stock", current_stock)
    demand = _validate_non_negative("daily_demand", daily_demand)
    safety = _validate_non_negative("safety_stock", safety_stock)
    lead_time = _validate_non_negative("supplier_lead_time_days", supplier_lead_time_days)

    runway = calculate_runway(stock, demand)
    safety_gap = calculate_safety_stock_gap(stock, safety)
    coverage_gap = calculate_coverage_gap(runway, lead_time)
    risk = calculate_stockout_risk(runway, lead_time, safety_gap)
    requirement = calculate_reorder_requirement(stock, demand, safety, lead_time)

    return InventoryRiskResult(
        current_stock=stock,
        daily_demand=demand,
        safety_stock=safety,
        supplier_lead_time_days=lead_time,
        runway_days=runway,
        safety_stock_gap=safety_gap,
        coverage_gap=coverage_gap,
        stockout_risk=risk,
        reorder_requirement=requirement,
    )


def _validate_non_negative(name: str, value: Real) -> float:
    """Validate and normalize a finite, non-negative numeric input."""
    number = _validate_finite_number(name, value)
    if number < 0:
        raise ValueError(f"{name} must be non-negative")
    return number


def _validate_finite_number(name: str, value: Real) -> float:
    """Reject non-numeric, infinite, and NaN calculation inputs clearly."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number
