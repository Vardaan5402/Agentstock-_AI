"""Deterministic before/after comparison for AgentStock what-if scenarios."""

from datetime import datetime, timezone

from models.what_if import (
    BusinessScenarioOutcome,
    MetricDelta,
    SupplierOutcomeComparison,
    WhatIfComparisonResult,
)


def metric_delta(baseline, counterfactual) -> MetricDelta:
    change = None
    if isinstance(baseline, (int, float)) and isinstance(counterfactual, (int, float)) and not isinstance(baseline, bool) and not isinstance(counterfactual, bool):
        change = float(counterfactual) - float(baseline)
    return MetricDelta(
        baseline_value=baseline,
        counterfactual_value=counterfactual,
        numeric_change=change,
    )


def compare_supplier_outcomes(baseline: BusinessScenarioOutcome, counterfactual: BusinessScenarioOutcome) -> tuple[SupplierOutcomeComparison, ...]:
    """Compare matching suppliers by stable ID, preserving baseline order."""
    counter = {x.supplier_id: x for x in counterfactual.supplier_outcomes}
    comparisons = []
    for before in baseline.supplier_outcomes:
        after = counter.get(before.supplier_id)
        if after is None:
            continue
        bopt, aopt = before.purchase_option, after.purchase_option
        bs, ass = before.simulation_result, after.simulation_result
        br, ar = before.inventory_risk, after.inventory_risk
        comparisons.append(
            SupplierOutcomeComparison(
                supplier_id=before.supplier_id,
                runway_days=metric_delta(br.runway_days, ar.runway_days),
                stockout_risk=metric_delta(br.stockout_risk, ar.stockout_risk),
                stockout_day=metric_delta(bs.stockout_day, ass.stockout_day),
                total_shortage_units=metric_delta(bs.total_shortage_units, ass.total_shortage_units),
                purchase_quantity=metric_delta(bopt.purchase_quantity, aopt.purchase_quantity),
                purchase_cost=metric_delta(bopt.total_cost, aopt.total_cost),
                budget_remaining=metric_delta(bopt.budget_remaining, aopt.budget_remaining),
                coverage_gap=metric_delta(bopt.coverage_gap, aopt.coverage_gap),
                operational_feasibility=metric_delta(bopt.operationally_feasible, aopt.operationally_feasible),
                financial_feasibility=metric_delta(bopt.financially_feasible, aopt.financially_feasible),
                supplier_reliability=metric_delta(bopt.supplier_reliability, aopt.supplier_reliability),
            )
        )
    return tuple(comparisons)


def compare_business_outcomes(
    baseline: BusinessScenarioOutcome,
    counterfactual: BusinessScenarioOutcome,
) -> WhatIfComparisonResult:
    """Build a deterministic, unranked before/after comparison artifact."""
    if baseline.baseline_snapshot_id != counterfactual.baseline_snapshot_id:
        raise ValueError("baseline snapshot IDs do not match")
    return WhatIfComparisonResult(
        baseline_snapshot_id=baseline.baseline_snapshot_id,
        scenario_id=counterfactual.scenario_id,
        baseline_outcome=baseline,
        counterfactual_outcome=counterfactual,
        supplier_comparisons=compare_supplier_outcomes(baseline, counterfactual),
        generated_at=datetime.now(timezone.utc),
    )
