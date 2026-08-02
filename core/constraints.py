"""Deterministic supplier and cash feasibility checks for AgentStock."""

from enum import Enum
from math import isfinite
from numbers import Integral, Real
from typing import Iterable

from pydantic import BaseModel, Field, model_validator

from core.calculations import calculate_coverage_gap, calculate_runway
from models.inventory import Product
from models.supplier import Supplier, SupplierProduct


class ReasonCode(str, Enum):
    """Stable reason codes for purchase-option consumers."""

    FEASIBLE = "FEASIBLE"
    INSUFFICIENT_BUDGET = "INSUFFICIENT_BUDGET"
    SUPPLIER_LEAD_TIME_EXCEEDS_RUNWAY = "SUPPLIER_LEAD_TIME_EXCEEDS_RUNWAY"
    MULTIPLE_CONSTRAINT_FAILURES = "MULTIPLE_CONSTRAINT_FAILURES"
    NO_DEMAND_FORECAST = "NO_DEMAND_FORECAST"
    ZERO_REQUIRED_QUANTITY = "ZERO_REQUIRED_QUANTITY"


class BudgetFeasibilityResult(BaseModel):
    """The transparent financial result for a proposed purchase."""

    feasible: bool
    budget_remaining: float


class LeadTimeFeasibilityResult(BaseModel):
    """The operational coverage result for a proposed purchase."""

    feasible: bool
    coverage_gap: float | None
    reason_code: ReasonCode | None = None
    reason: str | None = None


class PurchaseOption(BaseModel):
    """A deterministic, unranked purchase option for one supplier/product pair."""

    option_id: str = Field(min_length=1)
    supplier_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    required_quantity: int = Field(ge=0)
    purchase_quantity: int = Field(ge=0)
    unit_price: float = Field(ge=0)
    total_cost: float = Field(ge=0)
    available_budget: float = Field(ge=0)
    budget_remaining: float
    supplier_lead_time_days: float = Field(ge=0)
    inventory_runway_days: float | None
    coverage_gap: float | None
    supplier_reliability: float = Field(ge=0, le=1)
    financially_feasible: bool
    operationally_feasible: bool
    feasible: bool
    reason_code: ReasonCode | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def feasibility_must_match_constraints(self) -> "PurchaseOption":
        """Prevent a stored option from claiming feasibility incorrectly."""
        expected = self.financially_feasible and self.operationally_feasible
        if self.feasible != expected:
            raise ValueError(
                "feasible must equal financially_feasible and operationally_feasible"
            )
        return self


def calculate_purchase_quantity(
    required_quantity: Integral, minimum_order_quantity: Integral
) -> int:
    """Return required whole units, raised to MOQ only when units are required."""
    required = _validate_whole_non_negative("required_quantity", required_quantity)
    minimum = _validate_whole_positive("minimum_order_quantity", minimum_order_quantity)
    if required == 0:
        return 0
    return max(required, minimum)


def calculate_purchase_cost(quantity: Real, unit_price: Real) -> float:
    """Return the unrounded monetary cost of a purchase."""
    units = _validate_non_negative_number("quantity", quantity)
    price = _validate_non_negative_number("unit_price", unit_price)
    return units * price


def check_budget_feasibility(
    total_cost: Real, available_budget: Real
) -> BudgetFeasibilityResult:
    """Determine whether cost fits the supplied business-specific budget."""
    cost = _validate_non_negative_number("total_cost", total_cost)
    budget = _validate_non_negative_number("available_budget", available_budget)
    remaining = budget - cost
    return BudgetFeasibilityResult(feasible=cost <= budget, budget_remaining=remaining)


def check_lead_time_feasibility(
    inventory_runway_days: float | None, supplier_lead_time_days: Real
) -> LeadTimeFeasibilityResult:
    """Determine whether the supplier can arrive before inventory coverage ends.

    A ``None`` runway means demand is zero. No stockout forecast is invented;
    the result is operationally feasible with an explicit informational code.
    """
    lead_time = _validate_non_negative_number(
        "supplier_lead_time_days", supplier_lead_time_days
    )
    coverage_gap = calculate_coverage_gap(inventory_runway_days, lead_time)
    if inventory_runway_days is None:
        return LeadTimeFeasibilityResult(
            feasible=True,
            coverage_gap=None,
            reason_code=ReasonCode.NO_DEMAND_FORECAST,
            reason="No demand forecast is available; lead-time coverage is undefined.",
        )
    if coverage_gap < 0:
        return LeadTimeFeasibilityResult(
            feasible=False,
            coverage_gap=coverage_gap,
            reason_code=ReasonCode.SUPPLIER_LEAD_TIME_EXCEEDS_RUNWAY,
            reason="Supplier lead time exceeds current inventory coverage.",
        )
    return LeadTimeFeasibilityResult(feasible=True, coverage_gap=coverage_gap)


def build_purchase_option(
    supplier: Supplier,
    supplier_product: SupplierProduct,
    product: Product,
    available_budget: Real,
    required_quantity: Integral,
) -> PurchaseOption:
    """Build one unranked option after validating its known constraints."""
    _validate_supplier_relationship(supplier, supplier_product, product)
    budget = _validate_non_negative_number("available_budget", available_budget)
    required = _validate_whole_non_negative("required_quantity", required_quantity)

    purchase_quantity = calculate_purchase_quantity(
        required, supplier_product.minimum_order_quantity
    )
    total_cost = calculate_purchase_cost(purchase_quantity, supplier_product.unit_price)
    budget_result = check_budget_feasibility(total_cost, budget)

    # A zero requirement represents a valid no-purchase option, so an arrival
    # date cannot make that no-action option operationally infeasible.
    if required == 0:
        lead_time_result = LeadTimeFeasibilityResult(feasible=True, coverage_gap=None)
    else:
        runway = calculate_runway(product.current_stock, product.daily_demand)
        lead_time_result = check_lead_time_feasibility(runway, supplier.lead_time_days)

    runway = (
        None
        if required == 0
        else calculate_runway(product.current_stock, product.daily_demand)
    )
    reason_code, reason = _determine_reason(
        required, budget_result, lead_time_result
    )

    return PurchaseOption(
        option_id=f"{supplier.id}:{product.id}",
        supplier_id=supplier.id,
        product_id=product.id,
        required_quantity=required,
        purchase_quantity=purchase_quantity,
        unit_price=supplier_product.unit_price,
        total_cost=total_cost,
        available_budget=budget,
        budget_remaining=budget_result.budget_remaining,
        supplier_lead_time_days=supplier.lead_time_days,
        inventory_runway_days=runway,
        coverage_gap=lead_time_result.coverage_gap,
        supplier_reliability=supplier.reliability_score,
        financially_feasible=budget_result.feasible,
        operationally_feasible=lead_time_result.feasible,
        feasible=budget_result.feasible and lead_time_result.feasible,
        reason_code=reason_code,
        reason=reason,
    )


def evaluate_supplier_options(
    product: Product,
    suppliers: Iterable[Supplier],
    supplier_products: Iterable[SupplierProduct],
    available_budget: Real,
    required_quantity: Integral,
) -> list[PurchaseOption]:
    """Evaluate every valid relationship in input order without ranking options.

    Relationships whose supplier or product does not match are skipped. This
    avoids fabricating options for suppliers that do not supply this product.
    """
    supplier_by_id = {supplier.id: supplier for supplier in suppliers}
    options: list[PurchaseOption] = []
    for supplier_product in supplier_products:
        if supplier_product.product_id != product.id:
            continue
        supplier = supplier_by_id.get(supplier_product.supplier_id)
        if supplier is None or supplier.business_id != product.business_id:
            continue
        options.append(
            build_purchase_option(
                supplier,
                supplier_product,
                product,
                available_budget,
                required_quantity,
            )
        )
    return options


def _determine_reason(
    required_quantity: int,
    budget: BudgetFeasibilityResult,
    lead_time: LeadTimeFeasibilityResult,
) -> tuple[ReasonCode, str | None]:
    if required_quantity == 0:
        return ReasonCode.ZERO_REQUIRED_QUANTITY, "No purchase quantity is required."
    if not budget.feasible and not lead_time.feasible:
        return (
            ReasonCode.MULTIPLE_CONSTRAINT_FAILURES,
            "Purchase exceeds available budget and supplier lead time exceeds current inventory coverage.",
        )
    if not budget.feasible:
        return ReasonCode.INSUFFICIENT_BUDGET, "Purchase exceeds available budget."
    if not lead_time.feasible:
        return (
            ReasonCode.SUPPLIER_LEAD_TIME_EXCEEDS_RUNWAY,
            "Supplier lead time exceeds current inventory coverage.",
        )
    if lead_time.reason_code is ReasonCode.NO_DEMAND_FORECAST:
        return ReasonCode.NO_DEMAND_FORECAST, lead_time.reason
    return ReasonCode.FEASIBLE, None


def _validate_supplier_relationship(
    supplier: Supplier, supplier_product: SupplierProduct, product: Product
) -> None:
    if supplier.business_id != product.business_id:
        raise ValueError("supplier and product must belong to the same business")
    if supplier_product.supplier_id != supplier.id:
        raise ValueError("supplier_product does not belong to the supplied supplier")
    if supplier_product.product_id != product.id:
        raise ValueError("supplier_product does not belong to the supplied product")


def _validate_whole_non_negative(name: str, value: Integral) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be a whole number")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return int(value)


def _validate_whole_positive(name: str, value: Integral) -> int:
    number = _validate_whole_non_negative(name, value)
    if number == 0:
        raise ValueError(f"{name} must be greater than zero")
    return number


def _validate_non_negative_number(name: str, value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    if number < 0:
        raise ValueError(f"{name} must be non-negative")
    return number
