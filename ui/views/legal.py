"""Legal Governance, Privacy Policy, Acceptable Use, and GDPR Data Management."""
import json
import streamlit as st
from database.database import Database
from ui.views.auth import get_current_user
from ui.components import render_section_header


def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())


def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


def render_legal_view(database: Database):
    """Render Legal Agreements, Privacy Policy, Acceptable Use, and GDPR Data Tools."""
    user = get_current_user(database)

    _h(
        """
        <div style="margin-bottom: 24px;">
            <div style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 0.12em; text-transform: uppercase;">
                ⚖️ TRUST & COMPLIANCE
            </div>
            <h1 style="font-size: 32px; font-weight: 800; letter-spacing: -0.02em; margin: 0; color: #FFFFFF;">
                Legal Terms, Privacy & Data Rights
            </h1>
            <div style="font-size: 14px; color: var(--muted); margin-top: 4px;">
                Commercial policies governing the use of AgentStock AI, biometric privacy, and self-service data management.
            </div>
        </div>
        """
    )

    tab_privacy, tab_aup, tab_terms, tab_data = st.tabs([
        "🔒 Privacy Policy",
        "🛡️ Acceptable Use Policy",
        "📜 Terms of Service",
        "📥 My Data & Account Rights (GDPR)",
    ])

    # =========================================================================
    # TAB 1: PRIVACY POLICY
    # =========================================================================
    with tab_privacy:
        _h(
            """
            <div class="agent-card">
                <h3>1. Commitment to Biometric & Visual Privacy</h3>
                <p style="color: #CBD5E1; line-height: 1.6;">
                    AgentStock AI is strictly engineered for <strong>physical inventory intelligence</strong>.
                    Our AI Camera Scanner is designed to scan barcodes, shelf labels, and cardboard cartons.
                    We enforce real-time <strong>Privacy Person Detection</strong> that automatically rejects, blurs, or discards frames containing human beings.
                    <strong>We do NOT perform facial recognition, identity tracking, biometric profiling, or worker surveillance.</strong>
                </p>

                <h3>2. Multi-Tenant Data Isolation</h3>
                <p style="color: #CBD5E1; line-height: 1.6;">
                    All product catalogs, supplier telephone numbers, purchase order records, and cost structures are strictly tenant-isolated.
                    Your business data is never shared with, leaked to, or accessible by any other tenant or competitor.
                </p>

                <h3>3. No Selling of Business Data</h3>
                <p style="color: #CBD5E1; line-height: 1.6;">
                    AgentStock AI does not sell, rent, or monetize your inventory records, purchase orders, or pricing agreements to third-party data brokers.
                </p>
            </div>
            """
        )

    # =========================================================================
    # TAB 2: ACCEPTABLE USE POLICY (AUP)
    # =========================================================================
    with tab_aup:
        _h(
            """
            <div class="agent-card">
                <h3>Permitted Use</h3>
                <p style="color: #CBD5E1; line-height: 1.6;">
                    AgentStock AI is exclusively licensed for legitimate commercial inventory management, supply chain forecasting,
                    shelf-stock counting, and purchase order communications with commercial suppliers.
                </p>

                <h3>Strictly Prohibited Activities</h3>
                <ul style="color: #CBD5E1; line-height: 1.7;">
                    <li>Surveillance, monitoring, or biometric tracking of retail employees or shoppers.</li>
                    <li>Scanning or attempting to analyze weapons, hazardous substances, illicit drugs, or illegal contraband.</li>
                    <li>Generating fraudulent invoices, falsified purchase orders, or unauthorized financial records.</li>
                    <li>Harassment, spamming, or automated bulk unsolicited messaging to suppliers via WhatsApp or Phone dialers.</li>
                    <li>Attempting prompt injection, reverse-engineering, jailbreaking, or exploiting platform security controls.</li>
                </ul>
            </div>
            """
        )

    # =========================================================================
    # TAB 3: TERMS OF SERVICE
    # =========================================================================
    with tab_terms:
        _h(
            """
            <div class="agent-card">
                <h3>Subscription Billing & Cancellations</h3>
                <p style="color: #CBD5E1; line-height: 1.6;">
                    Subscriptions are billed in advance on a monthly or annual cycle via Razorpay.
                    You may cancel your subscription at any time; your entitlements will remain active until the conclusion of your current billing cycle.
                </p>

                <h3>Fact-Bounded AI Disclaimers</h3>
                <p style="color: #CBD5E1; line-height: 1.6;">
                    AgentStock AI provides deterministic calculations and AI-assisted recommendations.
                    Business owners and authorized managers retain ultimate responsibility for approving purchase orders, entering contracts with suppliers, and managing physical stock levels.
                </p>
            </div>
            """
        )

    # =========================================================================
    # TAB 4: GDPR SELF-SERVICE DATA MANAGEMENT
    # =========================================================================
    with tab_data:
        st.markdown("### 📥 Self-Service Data Rights (GDPR / CCPA)")

        if not user:
            st.warning("Please sign in to access your business data management tools.")
            return

        c_exp, c_del = st.columns(2)

        with c_exp:
            with st.container(border=True):
                st.markdown("#### 📦 Export My Business Data")
                st.caption("Download all your business profiles, products, suppliers, and communication logs in standard JSON format.")

                if st.button("Generate Full Data Export (JSON)", type="primary", key="btn_exp_data"):
                    export_data = database.export_user_data(user.id)
                    json_str = json.dumps(export_data, indent=2)
                    st.download_button(
                        label="⬇️ Download agentstock_export.json",
                        data=json_str,
                        file_name=f"agentstock_export_{user.id[:8]}.json",
                        mime="application/json",
                        key="btn_dl_json",
                    )
                    st.success("✓ Data export ready for download.")

        with c_del:
            with st.container(border=True):
                st.markdown("#### ⚠️ Delete Account & Business Data")
                st.caption("Permanently delete your products, suppliers, and business profiles. This action cannot be undone.")

                confirm_delete = st.checkbox("I understand that all my inventory and catalog records will be permanently erased.", key="chk_del_acc")
                if st.button("Permanently Delete My Data", key="btn_del_acc", disabled=not confirm_delete):
                    database.delete_user_account_data(user.id)
                    st.session_state["is_logged_in"] = False
                    st.session_state["authenticated_user"] = None
                    st.success("✓ Your account data and catalogs have been permanently deleted.")
                    st.rerun()
