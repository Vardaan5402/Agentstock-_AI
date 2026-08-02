"""Deterministic what-if scenario derivation and evaluation for AgentStock."""

from math import ceil, isfinite
from numbers import Integral, Real
from typing import Iterable

from core.calculations import analyze_inventory_risk
from core.constraints import PurchaseOption, evaluate_supplier_options
from core.simulator import simulate_options
from models.inventory import Product
from models.supplier import Supplier, SupplierProduct
from models.what_if import (
    AdjustmentMode,
    AppliedShock,
    BusinessScenarioBaseline,
    BusinessScenarioOutcome,
    CounterfactualBusinessState,
    NumericShock,
    SupplierOutcome,
    WhatIfScenario,
)


def build_business_scenario_baseline(
    business,
    product: Product,
    suppliers: Iterable[Supplier],
    supplier_products: Iterable[SupplierProduct],
    available_budget: Real,
    simulation_days: Integral,
) -> BusinessScenarioBaseline:
    """Create a canonical immutable baseline with a deterministic snapshot ID."""
    suppliers_tuple = tuple(suppliers)
    supplier_products_tuple = tuple(supplier_products)
    budget = _non_negative("available_budget", available_budget)
    days = _whole_non_negative("simulation_days", simulation_days)
    payload = {
        "business": business.model_dump(mode="json"),
        "product": product.model_dump(mode="json"),
        "suppliers": [x.model_dump(mode="json") for x in suppliers_tuple],
        "supplier_products": [x.model_dump(mode="json") for x in supplier_products_tuple],
        "available_budget": budget,
        "simulation_days": days,
    }
    from models.what_if import calculate_baseline_snapshot_id
    snapshot_id = calculate_baseline_snapshot_id(payload)
    return BusinessScenarioBaseline(
        baseline_snapshot_id=snapshot_id,
        business=business,
        product=product,
        suppliers=suppliers_tuple,
        supplier_products=supplier_products_tuple,
        available_budget=budget,
        simulation_days=days,
    )


def validate_shocks(baseline: BusinessScenarioBaseline, scenario: WhatIfScenario) -> None:
    """Validate scenario targets against the immutable baseline relationships."""
    supplier_ids = {supplier.id for supplier in baseline.suppliers}
    pair_keys = {(x.supplier_id, x.product_id) for x in baseline.supplier_products}
    seen: set[tuple[object, str | None]] = set()
    for shock in scenario.shocks:
        key = (shock.target, shock.supplier_id)
        if key in seen:
            raise ValueError("scenario contains conflicting shocks for the same target")
        seen.add(key)
        if shock.supplier_id is not None and shock.supplier_id not in supplier_ids:
            raise ValueError(f"unknown supplier_id: {shock.supplier_id}")
        if shock.target.value in {"SUPPLIER_PRICE", "MOQ"}:
            if (shock.supplier_id, baseline.product.id) not in pair_keys:
                raise ValueError("price/MOQ shock requires a valid supplier-product relationship")
        if not isfinite(float(shock.value)):
            raise ValueError("shock value must be finite")


def apply_numeric_shock(baseline_value: Real, shock: NumericShock) -> float:
    """Apply SET, DELTA, or PERCENTAGE deterministically without rounding."""
    base = _non_negative("baseline_value", baseline_value)
    value = float(shock.value)
    if not isfinite(value):
        raise ValueError("shock value must be finite")
    if shock.mode is AdjustmentMode.SET:
        derived = value
    elif shock.mode is AdjustmentMode.DELTA:
        derived = base + value
    else:
        derived = base * (1.0 + value / 100.0)
    if not isfinite(derived) or derived < 0:
        raise ValueError(f"shock produces invalid negative/non-finite value: {derived}")
    return derived


def derive_counterfactual_state(
    baseline: BusinessScenarioBaseline, scenario: WhatIfScenario
) -> CounterfactualBusinessState:
    """Derive copies of product/suppliers/commercial terms without mutation."""
    validate_shocks(baseline, scenario)
    product = baseline.product.model_copy(deep=True)
    suppliers = [x.model_copy(deep=True) for x in baseline.suppliers]
    terms = [x.model_copy(deep=True) for x in baseline.supplier_products]
    applied: list[AppliedShock] = []

    for shock in scenario.shocks:
        if shock.target.value == "DEMAND":
            old = product.daily_demand
            new = apply_numeric_shock(old, shock)
            product = product.model_copy(update={"daily_demand": new})
        elif shock.target.value == "INVENTORY":
            old = product.current_stock
            new = apply_numeric_shock(old, shock)
            if not new.is_integer():
                raise ValueError("inventory shock must produce a whole number of units")
            product = product.model_copy(update={"current_stock": int(new)})
        elif shock.target.value == "AVAILABLE_BUDGET":
            old = baseline.available_budget
            new = apply_numeric_shock(old, shock)
            budget = new
        elif shock.target.value == "SUPPLIER_LEAD_TIME":
            supplier = next(x for x in suppliers if x.id == shock.supplier_id)
            old = supplier.lead_time_days
            new = apply_numeric_shock(old, shock)
            suppliers[suppliers.index(supplier)] = supplier.model_copy(update={"lead_time_days": new})
        elif shock.target.value == "SUPPLIER_RELIABILITY":
            supplier = next(x for x in suppliers if x.id == shock.supplier_id)
            old = supplier.reliability_score
            new = apply_numeric_shock(old, shock)
            if new > 1:
                raise ValueError("supplier reliability must remain within 0-1")
            suppliers[suppliers.index(supplier)] = supplier.model_copy(update={"reliability_score": new})
        elif shock.target.value in {"SUPPLIER_PRICE", "MOQ"}:
            index = next(
                i for i, x in enumerate(terms)
                if x.supplier_id == shock.supplier_id and x.product_id == baseline.product.id
            )
            term = terms[index]
            if shock.target.value == "SUPPLIER_PRICE":
                old = term.unit_price
                new = apply_numeric_shock(old, shock)
                terms[index] = term.model_copy(update={"unit_price": new})
            else:
                old = term.minimum_order_quantity
                new = apply_numeric_shock(old, shock)
                if not new.is_integer() or new <= 0:
                    raise ValueError("MOQ shock must produce a positive whole number")
                terms[index] = term.model_copy(update={"minimum_order_quantity": int(new)})
        else:
            raise ValueError(f"unsupported shock target: {shock.target}")

        applied.append(
            AppliedShock(
                target=shock.target,
                mode=shock.mode,
                supplier_id=shock.supplier_id,
                baseline_value=float(old),
                requested_value=float(shock.value),
                derived_value=float(new),
            )
        )

    budget = locals().get("budget", baseline.available_budget)
    return CounterfactualBusinessState(
        baseline_snapshot_id=baseline.baseline_snapshot_id,
        scenario_id=scenario.scenario_id,
        derived_product=product,
        derived_suppliers=tuple(suppliers),
        derived_supplier_products=tuple(terms),
        derived_available_budget=budget,
        applied_shocks=tuple(applied),
    )


def _evaluate_state(
    baseline_snapshot_id: str,
    scenario_id: str,
    product: Product,
    suppliers: tuple[Supplier, ...],
    supplier_products: tuple[SupplierProduct, ...],
    available_budget: float,
    simulation_days: int,
    derived_state: CounterfactualBusinessState,
) -> BusinessScenarioOutcome:
    """Run the existing deterministic engines for one state."""
    options: list[PurchaseOption] = []
    risks = {}
    for supplier in suppliers:
        risk = analyze_inventory_risk(
            product.current_stock,
            product.daily_demand,
            product.safety_stock,
            supplier.lead_time_days,
        )
        risks[supplier.id] = risk
        required = int(ceil(risk.reorder_requirement))
        options.extend(
            evaluate_supplier_options(
                product,
                (supplier,),
                supplier_products,
                available_budget,
                required,
            )
        )
    simulations = simulate_options(product.current_stock, product.daily_demand, simulation_days, options)
    simulation_by_id = {x.scenario_id: x for x in simulations}
    outcomes: list[SupplierOutcome] = []
    for option in options:
        simulation = simulation_by_id[f"PURCHASE_{option.option_id}"]
        outcomes.append(
            SupplierOutcome(
                supplier_id=option.supplier_id,
                inventory_risk=risks[option.supplier_id],
                purchase_option=option,
                simulation_result=simulation,
            )
        )
    return BusinessScenarioOutcome(
        baseline_snapshot_id=baseline_snapshot_id,
        scenario_id=scenario_id,
        derived_state=derived_state,
        purchase_options=tuple(options),
        simulations=tuple(simulations),
        supplier_outcomes=tuple(outcomes),
    )


def evaluate_business_state(baseline: BusinessScenarioBaseline, state: CounterfactualBusinessState) -> BusinessScenarioOutcome:
    """Evaluate a derived state through the Milestones 2–4 engines."""
    return _evaluate_state(
        baseline.baseline_snapshot_id,
        state.scenario_id,
        state.derived_product,
        state.derived_suppliers,
        state.derived_supplier_products,
        state.derived_available_budget,
        baseline.simulation_days,
        state,
    )


def evaluate_baseline(baseline: BusinessScenarioBaseline) -> BusinessScenarioOutcome:
    """Evaluate the baseline through exactly the same pipeline."""
    state = CounterfactualBusinessState(
        baseline_snapshot_id=baseline.baseline_snapshot_id,
        scenario_id="BASELINE",
        derived_product=baseline.product,
        derived_suppliers=baseline.suppliers,
        derived_supplier_products=baseline.supplier_products,
        derived_available_budget=baseline.available_budget,
        applied_shocks=(),
    )
    return evaluate_business_state(baseline, state)


def run_what_if(baseline: BusinessScenarioBaseline, scenario: WhatIfScenario):
    """Evaluate baseline and one counterfactual scenario."""
    state = derive_counterfactual_state(baseline, scenario)
    return evaluate_baseline(baseline), evaluate_business_state(baseline, state)


def _non_negative(name: str, value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


def _whole_non_negative(name: str, value: Integral) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError(f"{name} must be a non-negative whole number")
    return int(value)
