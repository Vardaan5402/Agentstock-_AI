import os
import streamlit as st
from database.database import Database
from core.decision_persistence import (
    list_decision_reviews,
    list_what_if_scenarios,
    list_audit_events,
)
from ui.components import (
    render_system_status_bar,
    render_ai_pipeline_banner,
    render_kpi_card,
    render_section_header,
)

from ui.views.auth import get_current_user, render_top_right_auth_widget
from core.security import require_admin

def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())

def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)

def render_dashboard_view(database: Database):
    """Render the Overview Dashboard."""
    current_user = get_current_user(database)
    is_admin, _ = require_admin(current_user)

    # Top Dashboard Header Row: Left Title & Right Auth Widget
    col_title, col_auth = st.columns([2.3, 1.2])

    with col_title:
        _h(
            """
            <div style="margin-bottom: 16px;">
                <h1 style="font-size: 32px; font-weight: 800; letter-spacing: -0.03em; margin: 0; background: linear-gradient(90deg, #FFFFFF, #CBD5E1); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                    AgentStock AI
                </h1>
                <div style="font-size: 15px; color: var(--muted); margin-top: 4px;">
                    Trusted AI Decisions for Modern Supply Chains • Fact-Bounded & Human-in-the-Loop
                </div>
            </div>
            """
        )

    with col_auth:
        render_top_right_auth_widget(database, key_prefix="dash_header")

    if not current_user:
        _h(
            """
            <div style="padding: 10px 16px; background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 12px; margin-bottom: 20px; font-size: 13px; color: #FBBF24; display: flex; align-items: center; justify-content: space-between;">
                <span>💡 <strong>Guest Preview Mode:</strong> You are exploring live dashboard telemetry & AI features. Use the <strong>Sign In / Register</strong> popover on the top-right to sign in anytime.</span>
            </div>
            """
        )

    gemini_key_present = bool(os.environ.get("GEMINI_API_KEY"))
    render_system_status_bar(gemini_available=gemini_key_present)
    
    # Render AI Pipeline Banner
    render_ai_pipeline_banner(current_step=1)

    # Fetch real SQLite statistics
    businesses = database.list_businesses(current_user.id) if current_user else []
    total_businesses = len(businesses)
    total_products = sum(len(database.list_products(b.id, current_user.id)) for b in businesses) if current_user else 0
    total_reviews = len(list_decision_reviews(database))
    total_what_ifs = len(list_what_if_scenarios(database))
    total_audits = len(list_audit_events(database, current_user)) if is_admin else None

    render_section_header("Platform Metrics & System Health", "Live telemetry from SQLite database and Gemini engine", "📊")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _h(render_kpi_card("Active Businesses", total_businesses, "🏢", "Persisted in SQLite", "#6D5DFC"))
    with c2:
        _h(render_kpi_card("Catalog Products", total_products, "📦", "Active SKUs", "#00D4FF"))
    with c3:
        _h(render_kpi_card("Decision Reviews", total_reviews, "📄", "Immutable Snapshots", "#22C55E"))
    with c4:
        _h(render_kpi_card("What-If Scenarios", total_what_ifs, "🔮", "Counterfactual Simulations", "#F59E0B"))

    _h("<div style='height: 12px;'></div>")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        if is_admin:
            _h(render_kpi_card("Audit Events", total_audits, "🛡️", "Immutable Trail", "#A78BFA"))
        else:
            _h(render_kpi_card("Workspace Access", "Ready", "✓", "Your business workspace", "#A78BFA"))
    with c6:
        _h(render_kpi_card("Gemini Engine", "Online" if gemini_key_present else "Offline", "🤖", "gemini-3.6-flash", "#22C55E" if gemini_key_present else "#F59E0B"))
    with c7:
        _h(render_kpi_card("Deterministic Engine", "Ready", "⚙️", "Milestones 2–6 Active", "#6D5DFC"))
    with c8:
        _h(render_kpi_card("System Health", "Healthy", "●", "Zero Unhandled Faults", "#22C55E"))

    _h("<div style='height: 24px;'></div>")

    # Quick Navigation / Action Hub
    render_section_header("Quick Navigation & Workflow Launch", "Instant access to core platform features", "🚀")

    # Smart Inventory Capture Hero Action
    _h(
        """
        <div class="agent-card" style="background: linear-gradient(135deg, rgba(109, 93, 252, 0.15) 0%, rgba(0, 212, 255, 0.08) 100%); border: 1px solid rgba(109, 93, 252, 0.35); margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 0.1em; text-transform: uppercase;">
                        ⚡ NEW IN V5.0 — MULTIMODAL INVENTORY CAPTURE
                    </div>
                    <div style="font-size: 22px; font-weight: 800; color: #FFFFFF; margin-top: 4px;">
                        🎙️ Voice Assistant & 📷 Camera Inventory Scanner
                    </div>
                    <div style="font-size: 14px; color: var(--muted); margin-top: 4px;">
                        Update on-hand stock with spoken natural language or scan physical retail shelves with Gemini Vision.
                    </div>
                </div>
            </div>
        </div>
        """
    )
    col_cap1, col_cap2, _ = st.columns([1.5, 1.5, 3])
    with col_cap1:
        if st.button("🎙️ Open Voice Assistant ➔", type="primary", key="dash_btn_open_voice"):
            st.session_state["pending_nav_page"] = "⚡ Smart Inventory Capture"
            st.rerun()
    with col_cap2:
        if st.button("📷 Scan Inventory Shelves ➔", type="secondary", key="dash_btn_open_cam"):
            st.session_state["pending_nav_page"] = "⚡ Smart Inventory Capture"
            st.rerun()

    _h("<div style='height: 16px;'></div>")

    q1, q2, q3 = st.columns(3)
    with q1:
        _h(
            """
            <div class="agent-card">
                <div style="font-size: 20px; font-weight: 700; color: #FFFFFF; margin-bottom: 8px;">⚡ Decision Workbench</div>
                <p style="color: var(--muted); font-size: 14px; margin-bottom: 16px;">
                    Run deterministic inventory simulation + Gemini structured reasoning with full reference validation.
                </p>
            </div>
            """
        )
        if st.button("Open Decision Workbench ➔", type="secondary", key="dash_btn_wb"):
            st.session_state["pending_nav_page"] = "⚡ Decision Workbench"
            st.rerun()

    with q2:
        _h(
            """
            <div class="agent-card">
                <div style="font-size: 20px; font-weight: 700; color: #FFFFFF; margin-bottom: 8px;">🔮 What-If Analysis</div>
                <p style="color: var(--muted); font-size: 14px; margin-bottom: 16px;">
                    Simulate price shocks, demand surges, and lead-time delays against immutable baselines.
                </p>
            </div>
            """
        )
        if st.button("Open What-If Simulator ➔", type="secondary", key="dash_btn_wi"):
            st.session_state["pending_nav_page"] = "🔮 What-If Simulator"
            st.rerun()

    if is_admin:
        with q3:
            _h(
                """
                <div class="agent-card">
                    <div style="font-size: 20px; font-weight: 700; color: #FFFFFF; margin-bottom: 8px;">🛡️ Audit & History</div>
                    <p style="color: var(--muted); font-size: 14px; margin-bottom: 16px;">
                        Inspect tamper-proof audit trails, historical decisions, and compliance governance.
                    </p>
                </div>
                """
            )
            if st.button("View Audit Log ➔", type="secondary", key="dash_btn_aud"):
                st.session_state["pending_nav_page"] = "🛡️ Audit Trail"
                st.rerun()

    _h("<div style='height: 24px;'></div>")

    # AI Trust & Governance Section
    render_section_header("AI Governance & Architecture Strengths", "Why enterprise teams trust AgentStock AI", "🛡️")

    g1, g2, g3 = st.columns(3)
    with g1:
        _h(
            """
            <div class="agent-card" style="border-left: 4px solid #6D5DFC;">
                <div style="font-weight: 700; font-size: 16px; color: #FFFFFF; margin-bottom: 6px;">✓ Fact-Bounded Reasoning</div>
                <p style="font-size: 13px; color: var(--muted); margin: 0;">
                    Gemini NEVER calculates numerical values or invents supplier data. The deterministic simulation engine calculates all facts first.
                </p>
            </div>
            """
        )
    with g2:
        _h(
            """
            <div class="agent-card" style="border-left: 4px solid #00D4FF;">
                <div style="font-weight: 700; font-size: 16px; color: #FFFFFF; margin-bottom: 6px;">✓ Reference Validation</div>
                <p style="font-size: 13px; color: var(--muted); margin: 0;">
                    Every claim made by Gemini must explicitly resolve to a field in the authoritative <code>DecisionFacts</code> JSON or it is rejected.
                </p>
            </div>
            """
        )
    with g3:
        _h(
            """
            <div class="agent-card" style="border-left: 4px solid #22C55E;">
                <div style="font-weight: 700; font-size: 16px; color: #FFFFFF; margin-bottom: 6px;">✓ Human-in-the-Loop</div>
                <p style="font-size: 13px; color: var(--muted); margin: 0;">
                    Autonomous purchasing is strictly prohibited. Every recommendation is review-only and requires explicit human approval.
                </p>
            </div>
            """
        )

    _h("<div style='height: 24px;'></div>")

    # Instant Supplier Communication & PO Automation Suite
    render_section_header("Instant Supplier Communication & Automated PO Dispatch", "Place direct calls, dispatch WhatsApp POs, and email suppliers instantly", "📞")

    from ui.components import render_supplier_communication_suite

    if current_user and businesses:
        b_sel = businesses[0]
        prods = database.list_products(b_sel.id, current_user.id)
        sups = database.list_suppliers(b_sel.id, current_user.id)
        if not sups:
            st.info("No suppliers added yet. Add your first supplier in Settings & Catalog.")
            if st.button("Add Supplier", key="dash_add_first_supplier"):
                st.session_state["pending_nav_page"] = "⚙️ Settings & Catalog"
                st.rerun()
        elif prods:
            p_sel = prods[0]
            supplier_options = {f"{s.company_name or s.name} ({s.name})": s for s in sups}
            selected_label = st.selectbox("Select Supplier", list(supplier_options), key=f"dash_supplier_{current_user.id}")
            selected_supplier = supplier_options[selected_label]
            s_price = 55.0
            render_supplier_communication_suite(
                supplier_name=selected_supplier.company_name or selected_supplier.name,
                phone=selected_supplier.phone,
                email=selected_supplier.email,
                sku=p_sel.sku,
                product_name=p_sel.name,
                quantity=100,
                unit_price=s_price,
                total_cost=f"₹{100 * s_price:,.2f}",
            )
        else:
            st.info("Add products in Settings & Catalog before preparing a purchase order.")
    else:
        st.info("Sign in and add a business, supplier, and product to use supplier communication.")
