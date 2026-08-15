import streamlit as st
from database.database import Database
from core.decision_persistence import (
    list_decision_reviews,
    get_decision_review,
    list_what_if_scenarios,
    get_what_if_scenario,
)
from core.decision_context import derive_required_uncertainties
from ui.components import render_section_header

def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())

def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)

def render_history_view(database: Database):
    """Render the Decision History view."""
    _h(
        """
        <div style="margin-bottom: 20px;">
            <h1 style="font-size: 30px; font-weight: 800; letter-spacing: -0.03em; margin: 0; color: #FFFFFF;">
                📜 Decision & What-If History
            </h1>
            <div style="font-size: 14px; color: var(--muted); margin-top: 4px;">
                Inspect read-only historical decision snapshots and saved counterfactual comparisons.
            </div>
        </div>
        """
    )

    tab1, tab2 = st.tabs(["📄 Decision Reviews", "🔮 What-If Scenarios"])

    with tab1:
        render_section_header("Saved Decision Reviews", "Read-only historical snapshots stored in SQLite", "📄")
        try:
            reviews = list_decision_reviews(database)
            if not reviews:
                st.info("No decision reviews saved yet. Run and save a review in the Decision Workbench.")
            else:
                f1, f2, f3 = st.columns(3)
                b_filter = f1.selectbox("Filter Business", ["All"] + sorted({r.business_id for r in reviews}), key="hist_b_filter")
                p_filter = f2.selectbox("Filter Product", ["All"] + sorted({r.product_id for r in reviews}), key="hist_p_filter")
                s_filter = f3.selectbox("Filter Status", ["All"] + sorted({r.status.value for r in reviews}), key="hist_s_filter")

                filtered_reviews = [
                    r for r in reviews
                    if (b_filter == "All" or r.business_id == b_filter)
                    and (p_filter == "All" or r.product_id == p_filter)
                    and (s_filter == "All" or r.status.value == s_filter)
                ]

                st.caption(f"Showing {len(filtered_reviews)} of {len(reviews)} decision reviews.")

                # Render review cards
                for r in filtered_reviews:
                    rec_scenario = r.proposal.selected_scenario_id if r.proposal else "DO_NOTHING"
                    confidence = r.proposal.confidence.value if r.proposal else "N/A"
                    status_badge = f'<span class="badge badge-primary">{r.status.value}</span>'
                    
                    _h(
                        f"""
                        <div class="agent-card">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                                <div>
                                    <div style="font-size: 16px; font-weight: 700; color: #FFFFFF;">
                                        Snapshot: <code style="color: var(--accent);">{r.snapshot_id[:16]}...</code>
                                    </div>
                                    <div style="font-size: 13px; color: var(--muted); margin-top: 2px;">
                                        Business: <strong>{r.business_id}</strong> | Product: <strong>{r.product_id}</strong> | Saved: {r.created_at.strftime('%Y-%m-%d %H:%M UTC')}
                                    </div>
                                </div>
                                <div>{status_badge}</div>
                            </div>
                            <div style="display: flex; gap: 16px; font-size: 13px; color: var(--text-secondary);">
                                <div>Selected Scenario: <strong style="color:#FFF;">{rec_scenario}</strong></div>
                                <div>Gemini Confidence: <strong style="color:var(--primary-light);">{confidence}</strong></div>
                            </div>
                        </div>
                        """
                    )
                    
                st.divider()
                selected_snap = st.selectbox("Select Decision Snapshot to Inspect", [r.snapshot_id for r in filtered_reviews], key="hist_snap_select")
                if st.button("👁️ Open Read-Only Decision Review", type="secondary", key="btn_open_hist_snap"):
                    st.session_state["opened_review"] = get_decision_review(database, selected_snap)

                opened_rev = st.session_state.get("opened_review")
                if opened_rev is not None:
                    render_section_header(f"Inspecting Snapshot {opened_rev.snapshot_id[:16]}", "Read-only verified facts and proposal", "🔍")
                    st.code(opened_rev.snapshot_id, language=None)
                    st.write("Saved Status:", opened_rev.status.value)
                    
                    with st.expander("View Deterministic DecisionFacts", expanded=False):
                        st.json(opened_rev.facts.model_dump(mode="json"))
                    with st.expander("View Purchase Options", expanded=False):
                        st.dataframe([opt.model_dump(mode="json") for opt in opened_rev.facts.purchase_options], hide_index=True)
                    with st.expander("View Gemini Proposal & Validations", expanded=False):
                        st.json({
                            "proposal": opened_rev.proposal.model_dump(mode="json") if opened_rev.proposal else None,
                            "reference_validation": opened_rev.reference_validation.model_dump(mode="json") if opened_rev.reference_validation else None,
                            "policy_validation": opened_rev.policy_validation.model_dump(mode="json") if opened_rev.policy_validation else None,
                        })

        except Exception as err:
            st.error(f"Failed to read decision history: {err}")

    with tab2:
        render_section_header("Saved What-If Counterfactual Scenarios", "Read-only what-if comparisons stored in SQLite", "🔮")
        try:
            saved_scenarios = list_what_if_scenarios(database)
            if not saved_scenarios:
                st.info("No what-if scenarios saved yet.")
            else:
                for item in saved_scenarios:
                    scen_name = getattr(item.scenario, "name", None) or (item.scenario.get("name") if isinstance(item.scenario, dict) else item.id[:12])
                    _h(
                        f"""
                        <div class="agent-card">
                            <div style="font-size: 16px; font-weight: 700; color: #FFFFFF; margin-bottom: 6px;">
                                Scenario: {scen_name}
                            </div>
                            <div style="font-size: 13px; color: var(--muted);">
                                Decision Snapshot: <code>{item.decision_snapshot_id[:12]}</code> | Baseline: <code>{item.baseline_snapshot_id[:12]}</code>
                            </div>
                        </div>
                        """
                    )
                st.divider()
                selected_scen_id = st.selectbox("Select What-If Scenario to Inspect", [s.id for s in saved_scenarios], key="hist_scen_select")
                if st.button("👁️ Open Saved What-If Comparison", type="secondary", key="btn_open_hist_scen"):
                    st.session_state["opened_what_if"] = get_what_if_scenario(database, selected_scen_id)

                opened_wi = st.session_state.get("opened_what_if")
                if opened_wi is not None:
                    with st.expander("🔍 View Raw What-If Comparison JSON", expanded=False):
                        st.json(opened_wi.model_dump(mode="json"))

        except Exception as err:
            st.error(f"Failed to read what-if history: {err}")
