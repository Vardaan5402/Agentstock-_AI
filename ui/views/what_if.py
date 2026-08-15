import streamlit as st
from database.database import Database
from models.what_if import ShockTarget, AdjustmentMode, NumericShock, WhatIfScenario
from core.what_if import run_what_if
from core.what_if_comparison import compare_business_outcomes
from core.decision_persistence import save_what_if_scenario
from ui.components import (
    render_section_header,
    render_what_if_delta_card,
)

def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())

def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)

def render_what_if_view(database: Database):
    """Render the What-If Counterfactual Simulator view."""
    _h(
        """
        <div style="margin-bottom: 20px;">
            <h1 style="font-size: 30px; font-weight: 800; letter-spacing: -0.03em; margin: 0; color: #FFFFFF;">
                🔮 What-If Counterfactual Simulator
            </h1>
            <div style="font-size: 14px; color: var(--muted); margin-top: 4px;">
                Derive counterfactual scenarios against an immutable decision baseline without mutating ground-truth facts.
            </div>
        </div>
        """
    )

    result = st.session_state.get("decision_workflow_result")
    if result is None:
        st.info("💡 Please generate or select a decision baseline in the **Decision Workbench** first to enable What-If simulation.")
        if st.button("Go to Decision Workbench ➔", type="primary", key="wi_btn_go_wb"):
            st.session_state["pending_nav_page"] = "⚡ Decision Workbench"
            st.rerun()
        return

    render_section_header("Configure Counterfactual Shock Parameters", "Adjust lead time, price, demand, or MOQ to evaluate scenario sensitivity", "⚙️")

    st.caption(f"Baseline Snapshot ID: `{result.baseline.baseline_snapshot_id}`")

    supplier_ids = [s.id for s in result.baseline.suppliers]
    supplier_names = {s.id: s.name for s in result.baseline.suppliers}

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        target_str = st.selectbox("Target Metric", [t.value for t in ShockTarget], key="wi_target")
    with c2:
        mode_str = st.selectbox("Adjustment Mode", [m.value for m in AdjustmentMode], key="wi_mode")
    with c3:
        val = st.number_input("Adjustment Value", value=25.0, key="wi_val")
    with c4:
        selected_target = ShockTarget(target_str)
        supplier_id = None
        if selected_target in {ShockTarget.SUPPLIER_LEAD_TIME, ShockTarget.SUPPLIER_PRICE, ShockTarget.MOQ, ShockTarget.SUPPLIER_RELIABILITY}:
            supplier_id = st.selectbox("Target Supplier", supplier_ids, format_func=lambda x: supplier_names.get(x, x), key="wi_sup")

    if st.button("🔮 Run What-If Simulation", type="primary", key="wi_btn_run"):
        try:
            scenario = WhatIfScenario(
                scenario_id="workbench-what-if",
                name=f"Shock: {target_str} ({mode_str} {val})",
                shocks=(NumericShock(target=selected_target, mode=AdjustmentMode(mode_str), value=val, supplier_id=supplier_id),),
            )
            baseline_outcome, counterfactual = run_what_if(result.baseline, scenario)
            st.session_state["what_if_comparison"] = compare_business_outcomes(baseline_outcome, counterfactual)
            st.session_state["what_if_scenario"] = scenario
            st.success("✓ Counterfactual scenario evaluated successfully!")
        except ValueError as err:
            st.error(f"What-If Simulation Error: {err}")

    comparison = st.session_state.get("what_if_comparison")
    if comparison is not None and comparison.baseline_snapshot_id == result.baseline.baseline_snapshot_id:
        render_section_header("BASELINE vs. WHAT-IF Comparison Cards", "Side-by-side metric deltas and feasibility shifts", "📊")

        for item in comparison.supplier_comparisons:
            sup_name = supplier_names.get(item.supplier_id, item.supplier_id)
            st.markdown(f"### Supplier: {sup_name}")

            col1, col2, col3 = st.columns(3)
            with col1:
                # Cost change
                c_delta = item.purchase_cost.numeric_change
                c_status = "improved" if c_delta < 0 else ("worsened" if c_delta > 0 else "neutral")
                c_str = f"₹{c_delta:+,.2f}"
                _h(
                    render_what_if_delta_card(
                        "Total Purchase Cost",
                        f"₹{item.purchase_cost.baseline_value:,.2f}",
                        f"₹{item.purchase_cost.counterfactual_value:,.2f}",
                        c_str,
                        c_status
                    )
                )

            with col2:
                # Coverage gap change
                g_delta = item.coverage_gap.numeric_change if item.coverage_gap.numeric_change is not None else 0
                g_status = "improved" if g_delta > 0 else ("worsened" if g_delta < 0 else "neutral")
                g_str = f"{g_delta:+.1f} Days"
                _h(
                    render_what_if_delta_card(
                        "Coverage Gap",
                        f"{item.coverage_gap.baseline_value:.1f}d" if item.coverage_gap.baseline_value else "—",
                        f"{item.coverage_gap.counterfactual_value:.1f}d" if item.coverage_gap.counterfactual_value else "—",
                        g_str,
                        g_status
                    )
                )

            with col3:
                # Shortage change
                s_delta = item.total_shortage_units.numeric_change
                s_status = "improved" if s_delta < 0 else ("worsened" if s_delta > 0 else "neutral")
                s_str = f"{s_delta:+} Units"
                _h(
                    render_what_if_delta_card(
                        "Stock Shortage",
                        f"{item.total_shortage_units.baseline_value} Units",
                        f"{item.total_shortage_units.counterfactual_value} Units",
                        s_str,
                        s_status
                    )
                )

            col4, col5 = st.columns(2)
            with col4:
                fin_b = "✓ Feasible" if item.financial_feasibility.baseline_value else "✕ Infeasible"
                fin_c = "✓ Feasible" if item.financial_feasibility.counterfactual_value else "✕ Infeasible"
                fin_status = "improved" if (not item.financial_feasibility.baseline_value and item.financial_feasibility.counterfactual_value) else ("worsened" if (item.financial_feasibility.baseline_value and not item.financial_feasibility.counterfactual_value) else "neutral")
                _h(render_what_if_delta_card("Financial Feasibility", fin_b, fin_c, f"{fin_b} ➔ {fin_c}", fin_status))
            with col5:
                op_b = "✓ Feasible" if item.operational_feasibility.baseline_value else "✕ Infeasible"
                op_c = "✓ Feasible" if item.operational_feasibility.counterfactual_value else "✕ Infeasible"
                op_status = "improved" if (not item.operational_feasibility.baseline_value and item.operational_feasibility.counterfactual_value) else ("worsened" if (item.operational_feasibility.baseline_value and not item.operational_feasibility.counterfactual_value) else "neutral")
                _h(render_what_if_delta_card("Operational Feasibility", op_b, op_c, f"{op_b} ➔ {op_c}", op_status))

            st.divider()

        # Save & Download buttons
        b1, b2 = st.columns(2)
        with b1:
            saved_snap_id = st.session_state.get("saved_decision_snapshot_id")
            if saved_snap_id != result.facts.snapshot_id:
                st.warning("⚠️ Save the decision review in the Workbench first before persisting what-if scenario to SQLite.")
            elif st.button("💾 Save What-If Scenario to Database", type="primary", key="wi_save_btn"):
                try:
                    scenario = st.session_state.get("what_if_scenario")
                    saved_s = save_what_if_scenario(database, saved_snap_id, scenario, comparison)
                    st.success(f"✓ Saved read-only What-If scenario ID: `{saved_s.id}`")
                except ValueError as err:
                    st.error(str(err))

        with b2:
            st.download_button(
                "📥 Download What-If Comparison JSON",
                data=comparison.model_dump_json(indent=2),
                file_name=f"agentstock-whatif-{comparison.baseline_snapshot_id[:10]}.json",
                mime="application/json",
                key="wi_dl_btn"
            )
