"""Platform Administration, System Telemetry, User RBAC & Security Alert Center."""
import os
import streamlit as st
from database.database import Database
from models.security import SecuritySeverity
from ui.views.auth import get_current_user
from ui.components import render_section_header, render_kpi_card
from core.config import (
    get_gemini_api_key,
    get_razorpay_key_id,
    get_smtp_config,
)
from core.security import require_admin


def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())


def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


def render_admin_dashboard(database: Database):
    """Render Enterprise Platform Admin Dashboard."""
    user = get_current_user(database)

    # Use the shared server-side authorization rule for every admin surface.
    authorized, _ = require_admin(user)
    if not authorized:
        _h(
            """
            <div style="background: rgba(239, 68, 68, 0.15); border: 1.5px solid #EF4444; border-radius: 14px; padding: 24px; text-align: center; max-width: 600px; margin: 60px auto;">
                <div style="font-size: 40px; margin-bottom: 8px;">🚫</div>
                <div style="font-size: 20px; font-weight: 800; color: #FFFFFF;">Access Denied</div>
                <div style="font-size: 14px; color: #CBD5E1; margin-top: 6px;">
                    This administrative portal is restricted to authorized platform administrators.
                </div>
            </div>
            """
        )
        return

    _h(
        """
        <div style="margin-bottom: 24px;">
            <div style="font-size: 11px; font-weight: 800; color: #F59E0B; letter-spacing: 0.12em; text-transform: uppercase;">
                👑 PLATFORM SUPERADMIN CONSOLE
            </div>
            <h1 style="font-size: 32px; font-weight: 800; letter-spacing: -0.02em; margin: 0; color: #FFFFFF;">
                AgentStock AI Operations & Security
            </h1>
            <div style="font-size: 14px; color: var(--muted); margin-top: 4px;">
                Platform telemetry, multi-tenant RBAC governance, security incident monitoring, and compliance retention.
            </div>
        </div>
        """
    )

    # 1. Telemetry Metrics Cards
    all_users = database.list_all_users()
    all_subs = database.list_all_subscriptions()
    active_subs = [s for s in all_subs if s.is_active and s.plan_name != "FREE"]
    all_prods = database.list_all_products()
    all_comms = database.list_supplier_communications()

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        _h(render_kpi_card("Registered Users", str(len(all_users)), "👥", f"{sum(1 for u in all_users if u.is_verified)} Verified", "#00D4FF"))
    with m2:
        _h(render_kpi_card("Active Paid Subscriptions", str(len(active_subs)), "💳", f"{len(all_subs)} Total Records", "#22C55E"))
    with m3:
        _h(render_kpi_card("Total Catalog Products", str(len(all_prods)), "📦", "Across all businesses", "#6D5DFC"))
    with m4:
        _h(render_kpi_card("PO Communications", str(len(all_comms)), "📨", "Dispatched to suppliers", "#F59E0B"))

    _h("<div style='height: 20px;'></div>")

    # 2. Main Admin Tabs
    tab_users, tab_security, tab_audit, tab_sys = st.tabs([
        "👥 User & Tenant Management",
        "🚨 Security Alerts & Threats",
        "📜 Audit Trail & Data Retention",
        "⚙️ System Health & Keys",
    ])

    # =========================================================================
    # TAB 1: USER MANAGEMENT
    # =========================================================================
    with tab_users:
        st.markdown("### 👥 Platform Users & RBAC")

        user_rows = []
        for u in all_users:
            user_rows.append({
                "User ID": u.id[:10] + "...",
                "Name": u.name,
                "Email": u.email,
                "Role": u.role,
                "Verified": "✓ Yes" if u.is_verified else "❌ Pending",
                "Status": "🔒 Locked" if u.is_locked else "🟢 Active",
                "Joined Date": u.created_at[:10] if u.created_at else "—",
            })
        st.dataframe(user_rows, use_container_width=True)

        st.markdown("#### ⚡ Inspect User Activity & Management")
        c_u1, c_u2 = st.columns(2)
        with c_u1:
            target_email = st.selectbox("Select User Email to Inspect:", [u.email for u in all_users], key="adm_sel_u_email")
            t_user = next((u for u in all_users if u.email == target_email), None)

        with c_u2:
            if t_user:
                lock_label = "🔓 Unlock Account" if t_user.is_locked else "🔒 Lock / Suspend Account"
                if st.button(lock_label, key="btn_toggle_lock"):
                    t_user.is_locked = not t_user.is_locked
                    database.update_user(t_user)
                    st.success(f"✓ Account status updated for {t_user.email}!")
                    st.rerun()

        if t_user:
            with st.expander(f"🔍 Detailed Activity History for {t_user.name} ({t_user.email})", expanded=True):
                u_details = database.get_user_detailed_activity(t_user.id)
                k1, k2, k3, k4 = st.columns(4)
                with k1:
                    st.metric("Locations", u_details.get("businesses_count", 0))
                with k2:
                    st.metric("Products", u_details.get("products_count", 0))
                with k3:
                    st.metric("Suppliers", u_details.get("suppliers_count", 0))
                with k4:
                    st.metric("Orders Dispatched", u_details.get("communications_count", 0))

                st.markdown("**Recent Orders & Communications:**")
                comms = u_details.get("recent_communications", [])
                if comms:
                    for c in comms[:5]:
                        st.markdown(f"- `[{c.get('created_at', '')[:19]}]` **{c.get('comm_type', '')}** to `{c.get('recipient', '')}` — Ref: `{c.get('order_reference', '')}`")
                else:
                    st.caption("No orders dispatched yet.")

                st.markdown("**User Activity Timeline:**")
                acts = u_details.get("activity_timeline", [])
                if acts:
                    for a in acts[:5]:
                        st.markdown(f"- `[{a.get('created_at', '')[:19]}]` **{a.get('title', '')}**: {a.get('description', '')}")
                else:
                    st.caption("No recorded activity yet.")

                st.markdown("**⚖️ Legal & Policy Consent Status:**")
                consent = database.get_latest_user_consent(t_user.email)
                has_accepted = database.has_accepted_current_policies(t_user.email)
                if consent:
                    st.markdown(
                        f"""
                        - **Status**: {'🟢 Current (Compliant)' if has_accepted else '🟡 Outdated (Re-consent Required)'}
                        - **Agreed At**: `{consent.agreed_at}`
                        - **Accepted Versions**: Terms: `v{consent.terms_version}`, Privacy: `v{consent.privacy_version}`, AUP: `v{consent.acceptable_use_version}`, Billing: `v{consent.subscription_policy_version}`, Comms: `v{consent.communication_policy_version}`, Security: `v{consent.data_security_policy_version}`
                        """
                    )
                else:
                    st.warning("⚠️ No policy consent record found for this user. User will be prompted on next login.")

    # =========================================================================
    # TAB 2: SECURITY ALERTS
    # =========================================================================
    with tab_security:
        st.markdown("### 🚨 Security Incident Stream")
        alerts = database.list_security_alerts()

        if not alerts:
            st.success("🟢 No security incidents detected. System is operating safely.")
        else:
            for al in alerts[:15]:
                sev_color = "#EF4444" if al.severity == "CRITICAL" else ("#F59E0B" if al.severity == "HIGH" else "#00D4FF")
                _h(
                    f"""
                    <div class="agent-card" style="border-left: 3px solid {sev_color}; margin-bottom: 10px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:{sev_color}; font-weight:800; font-size:12px;">[{al.severity}] {al.event_type}</span>
                            <span style="color:var(--muted); font-size:11px;">🕒 {al.created_at}</span>
                        </div>
                        <div style="color:#FFF; font-size:13px; margin-top:4px;">{al.description}</div>
                        <div style="color:var(--muted); font-size:11px; margin-top:2px;">IP: {al.ip_address or 'Unknown'} | User: {al.user_id or 'Anonymous'}</div>
                    </div>
                    """
                )

    # =========================================================================
    # TAB 3: AUDIT TRAIL & RETENTION
    # =========================================================================
    with tab_audit:
        st.markdown("### 📜 Immutable Admin Audit Ledger & Compliance Retention")

        c_ret1, c_ret2 = st.columns([2, 1])
        with c_ret1:
            st.caption("AgentStock AI maintains immutable append-only records for billing compliance and GDPR data portability.")
        with c_ret2:
            ret_days = st.selectbox("Log Retention Period", [30, 60, 90, 180, 365], index=2, key="adm_ret_days")
            if st.button("🧹 Clean Expired Logs", key="btn_clean_audit"):
                deleted_cnt = database.clean_audit_logs_retention(ret_days)
                st.success(f"✓ Removed {deleted_cnt} expired audit records older than {ret_days} days.")

        admin_events = database.list_admin_audit_events(limit=50)
        st.markdown(f"**Immutable Administrator Audit Records ({len(admin_events)} Displayed):**")
        if admin_events:
            aud_rows = []
            for a in admin_events:
                aud_rows.append({
                    "Event ID": a["id"][:8] + "...",
                    "Classification": a["security_classification"],
                    "Event Type": a["event_type"],
                    "User / Email": a["user_email"] or a["user_id"] or "System",
                    "Timestamp": a["created_at"],
                })
            st.dataframe(aud_rows, use_container_width=True)
        else:
            # Fallback to general audit events
            audit_events = database.list_audit_events()
            aud_rows = []
            for a in audit_events[:25]:
                aud_rows.append({
                    "Event ID": a["id"][:8] + "...",
                    "Entity Type": a["entity_type"],
                    "Event Type": a["event_type"],
                    "User": a["user_id"] or "System",
                    "Timestamp": a["created_at"],
                })
            st.dataframe(aud_rows, use_container_width=True)

    # =========================================================================
    # TAB 4: SYSTEM HEALTH & CONFIGURATION
    # =========================================================================
    with tab_sys:
        st.markdown("### ⚙️ System Diagnostics & Credentials")

        has_gemini = bool(get_gemini_api_key())
        has_razorpay = bool(get_razorpay_key_id())
        smtp_cfg = get_smtp_config()
        has_smtp = bool(smtp_cfg.get("host"))

        diag_items = [
            {"Component": "Gemini 2.5/3.6 Multimodal AI", "Status": "🟢 ONLINE" if has_gemini else "🟡 STANDALONE (Deterministic)", "Details": "Configured via GEMINI_API_KEY"},
            {"Component": "Razorpay Billing Gateway", "Status": "🟢 CONFIGURED" if has_razorpay else "🟡 TEST / SANDBOX", "Details": "Key ID: " + (get_razorpay_key_id() or "Sandbox Mode")[:10] + "..."},
            {"Component": "SMTP Email Dispatcher", "Status": "🟢 CONFIGURED" if has_smtp else "⚪ LOG-ONLY DISPATCH", "Details": f"Host: {smtp_cfg.get('host') or 'Local log'}"},
            {"Component": "SQLite / Postgres Storage", "Status": "🟢 CONNECTED (WAL Mode)", "Details": database.db_path},
        ]

        st.dataframe(diag_items, use_container_width=True)
