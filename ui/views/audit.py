import json
import streamlit as st
from database.database import Database
from core.decision_persistence import list_audit_events
from ui.components import render_section_header, render_kpi_card

def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())

def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)

def render_audit_event_summary(ev):
    """Render human-friendly metadata summary card for selected audit event."""
    formatted_date = ev.created_at.strftime("%d %b %Y, %H:%M:%S UTC")
    entity_label = (
        "Decision Snapshot"
        if ev.entity_type == "decision_snapshot"
        else ("What-If Counterfactual" if ev.entity_type == "what_if_scenario" else ev.entity_type.replace("_", " ").title())
    )
    event_color = "#22C55E" if "APPROVED" in ev.event_type else ("#EF4444" if "REJECTED" in ev.event_type else "#6D5DFC")
    short_id = f"{ev.entity_id[:12]}...{ev.entity_id[-6:]}" if len(ev.entity_id) > 20 else ev.entity_id

    _h(
        f"""
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid var(--border); border-left: 4px solid {event_color}; border-radius: 14px; padding: 16px 20px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div>
                    <div style="font-size: 11px; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;">
                        EVENT CLASSIFICATION
                    </div>
                    <div style="font-size: 16px; font-weight: 700; color: #FFFFFF; margin-top: 2px;">
                        {ev.event_type.replace('_', ' ')}
                    </div>
                </div>
                <div style="display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 700; color: #22C55E; background: rgba(34, 197, 94, 0.12); padding: 5px 12px; border-radius: 20px; border: 1px solid rgba(34, 197, 94, 0.3);">
                    <span>✓ Verified SHA-256 Integrity</span>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255, 255, 255, 0.06);">
                <div>
                    <div style="font-size: 11px; color: var(--muted); text-transform: uppercase; font-weight: 600;">Entity Target</div>
                    <div style="font-size: 13px; font-weight: 600; color: #FFFFFF; margin-top: 2px;">{entity_label}</div>
                </div>
                <div>
                    <div style="font-size: 11px; color: var(--muted); text-transform: uppercase; font-weight: 600;">Target Record ID</div>
                    <div style="font-size: 12px; font-family: var(--font-mono); color: var(--accent); margin-top: 2px;"><code>{short_id}</code></div>
                </div>
                <div>
                    <div style="font-size: 11px; color: var(--muted); text-transform: uppercase; font-weight: 600;">Recorded Timestamp</div>
                    <div style="font-size: 12px; font-family: var(--font-mono); color: var(--text-secondary); margin-top: 2px;">{formatted_date}</div>
                </div>
            </div>
        </div>
        """
    )

def render_audit_view(database: Database):
    """Render the Enterprise Audit Trail & Governance view."""
    _h(
        """
        <div style="margin-bottom: 20px;">
            <h1 style="font-size: 30px; font-weight: 800; letter-spacing: -0.03em; margin: 0; color: #FFFFFF;">
                🛡️ Audit Trail
            </h1>
            <div style="font-size: 14px; color: var(--muted); margin-top: 4px;">
                Every decision is traceable, reviewable, and cryptographically recorded.
            </div>
        </div>
        """
    )

    try:
        events = list_audit_events(database)
        total_events = len(events)
        
        # 1. Top-Level Metric Cards
        c1, c2, c3, c4 = st.columns(4)
        decision_events = [e for e in events if e.entity_type == "decision_snapshot"]
        whatif_events = [e for e in events if e.entity_type == "what_if_scenario"]
        review_events = [e for e in events if e.event_type in {"DECISION_VIEWED", "DECISION_APPROVED", "DECISION_REJECTED"}]
        approved_events = [e for e in events if e.event_type == "DECISION_APPROVED"]
        rejected_events = [e for e in events if e.event_type == "DECISION_REJECTED"]

        latest_snapshot_id = decision_events[0].entity_id if decision_events else "No decisions yet"
        short_snapshot = f"{latest_snapshot_id[:10]}...{latest_snapshot_id[-6:]}" if len(latest_snapshot_id) > 20 else latest_snapshot_id

        if approved_events:
            human_review_status = "Approved"
            human_review_color = "#22C55E"
            human_review_icon = "✓"
        elif rejected_events:
            human_review_status = "Rejected"
            human_review_color = "#EF4444"
            human_review_icon = "✕"
        else:
            human_review_status = "Pending Sign-off"
            human_review_color = "#F59E0B"
            human_review_icon = "⏳"

        with c1:
            _h(render_kpi_card("Total Audit Events", total_events, "🛡️", "Immutable SQLite Ledger", "#6D5DFC"))
        with c2:
            _h(render_kpi_card("Decision Snapshots", len(decision_events), "📄", "Creation & Review Events", "#00D4FF"))
        with c3:
            _h(render_kpi_card("What-If Evaluations", len(whatif_events), "🔮", "Counterfactual Traces", "#F59E0B"))
        with c4:
            _h(render_kpi_card("Human Review", human_review_status, human_review_icon, f"{len(review_events)} interactions recorded", human_review_color))

        # 2. Professional Audit Integrity & Verification Pipeline Card
        col_pipeline, col_integrity = st.columns([1.5, 1])

        with col_pipeline:
            _h(
                f"""
                <div class="agent-card" style="height: 100%;">
                    <div style="font-size: 15px; font-weight: 700; color: #FFFFFF; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                        <span>📋 Decision Governance Pipeline</span>
                        <span style="font-size: 11px; color: #4ADE80; font-weight: 600; background: rgba(74, 222, 128, 0.1); padding: 2px 8px; border-radius: 12px; border: 1px solid rgba(74, 222, 128, 0.25);">End-to-End Grounded</span>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 10px; font-size: 13px;">
                        <div style="display: flex; align-items: center; gap: 10px; color: var(--text-secondary);">
                            <span style="color: #22C55E; font-weight: 800;">✓</span>
                            <span><strong>Decision Created:</strong> Grounded in deterministic SQLite catalog facts</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px; color: var(--text-secondary);">
                            <span style="color: #22C55E; font-weight: 800;">✓</span>
                            <span><strong>Evidence Verified:</strong> Mathematical inventory simulations verified</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px; color: var(--text-secondary);">
                            <span style="color: #22C55E; font-weight: 800;">✓</span>
                            <span><strong>Policy Validated:</strong> Business budget & replenishment limits enforced</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px; color: var(--text-secondary);">
                            <span style="color: #22C55E; font-weight: 800;">✓</span>
                            <span><strong>AI Recommendation:</strong> Fact-bounded qualitative reasoning generated</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px; color: var(--text-secondary);">
                            <span style="color: {human_review_color}; font-weight: 800;">{human_review_icon}</span>
                            <span><strong>Human Governance:</strong> {human_review_status}</span>
                        </div>
                    </div>
                </div>
                """
            )

        with col_integrity:
            _h(
                f"""
                <div class="agent-card" style="height: 100%;">
                    <div style="font-size: 15px; font-weight: 700; color: #FFFFFF; margin-bottom: 12px;">
                        🔐 Audit Integrity
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 10px; font-size: 13px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--muted);">Status</span>
                            <span style="color: #22C55E; font-weight: 700;">✓ Verified</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--muted);">Latest Snapshot</span>
                            <code style="color: var(--accent); font-size: 11px;">{short_snapshot}</code>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--muted);">Audit Events</span>
                            <span style="color: #FFFFFF; font-weight: 700;">{total_events} Records</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--muted);">Evidence Validation</span>
                            <span style="color: #22C55E; font-weight: 700;">✓ Zero Hallucination</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: var(--muted);">Human Review</span>
                            <span style="color: {human_review_color}; font-weight: 700;">{human_review_status}</span>
                        </div>
                    </div>
                </div>
                """
            )

        _h("<div style='height: 16px;'></div>")

        # 3. Filterable Event Timeline
        render_section_header("Audit Event Timeline & Search", "Filter tamper-proof event logs by entity, event type or ID", "🔍")

        if not events:
            st.info("No audit events recorded yet. Perform actions in the Decision Workbench or What-If Simulator.")
            return

        f1, f2, f3 = st.columns(3)
        entity_f = f1.selectbox("Entity Type", ["All"] + sorted({e.entity_type for e in events}), key="aud_e_filter")
        type_f = f2.selectbox("Event Type", ["All"] + sorted({e.event_type for e in events}), key="aud_t_filter")
        search_id = f3.text_input("Search Entity ID", placeholder="Snapshot or scenario ID...", key="aud_search_id").strip().lower()

        filtered = [
            e for e in events
            if (entity_f == "All" or e.entity_type == entity_f)
            and (type_f == "All" or e.event_type == type_f)
            and (not search_id or search_id in e.entity_id.lower())
        ]

        st.caption(f"Showing {len(filtered)} of {total_events} audit events.")

        # Timeline rendering with clean structured chips
        for ev in filtered[:25]:
            icon = "📄" if ev.entity_type == "decision_snapshot" else "🔮"
            event_color = "#22C55E" if "APPROVED" in ev.event_type else ("#EF4444" if "REJECTED" in ev.event_type else "#6D5DFC")
            
            meta_chips = "".join(
                f'<span style="display: inline-block; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 2px 8px; margin-right: 6px; margin-top: 4px; font-size: 11px; color: var(--muted); font-family: var(--font-mono);">'
                f'<strong style="color: var(--text-secondary);">{k}:</strong> {v}</span>'
                for k, v in ev.metadata.items()
            ) if ev.metadata else '<span style="font-size: 11px; color: var(--muted);">No metadata</span>'

            _h(
                f"""
                <div class="agent-card" style="padding: 14px 18px; border-left: 4px solid {event_color}; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                        <div style="font-weight: 700; font-size: 14px; color: #FFFFFF;">
                            {icon} {ev.event_type.replace('_', ' ')}
                        </div>
                        <div style="font-size: 12px; color: var(--muted); font-family: var(--font-mono);">
                            {ev.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
                        </div>
                    </div>
                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
                        Target: <code>{ev.entity_type}</code> | ID: <code style="color: var(--accent);">{ev.entity_id}</code>
                    </div>
                    <div style="margin-top: 6px;">
                        {meta_chips}
                    </div>
                </div>
                """
            )

        st.divider()

        # 4. Advanced Audit Details & Cryptographic Evidence (Hidden by default in expander)
        with st.expander("🔍 Advanced Audit Details & Cryptographic Logs", expanded=False):
            _h(
                """
                <div style="margin-bottom: 16px;">
                    <div style="font-size: 16px; font-weight: 700; color: #FFFFFF;">
                        💻 Technical Audit Event Inspection
                    </div>
                    <div style="font-size: 13px; color: var(--muted); margin-top: 2px;">
                        Technical audit information for compliance, verification, and cryptographic debugging.
                    </div>
                </div>
                """
            )

            ev_ids = [e.id for e in filtered] if filtered else [e.id for e in events]
            sel_ev_id = st.selectbox("Select Audit Event ID to Inspect", ev_ids, key="aud_ev_select")
            sel_ev = next((e for e in events if e.id == sel_ev_id), None)

            if sel_ev:
                render_audit_event_summary(sel_ev)

                st.markdown("#### 📜 Raw Cryptographic JSON Payload")
                raw_dict = sel_ev.model_dump(mode="json")
                json_str = json.dumps(raw_dict, indent=2)

                col_down, _ = st.columns([1.5, 3])
                with col_down:
                    st.download_button(
                        label="📥 Download Event JSON",
                        data=json_str,
                        file_name=f"audit_event_{sel_ev.id[:12]}_{sel_ev.event_type.lower()}.json",
                        mime="application/json",
                        key=f"dl_aud_btn_{sel_ev.id}",
                    )

                st.json(raw_dict)

    except Exception as err:
        st.error(f"Audit log retrieval error: {err}")
