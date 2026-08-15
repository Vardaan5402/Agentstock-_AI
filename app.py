"""AgentStock AI — Enterprise AI Inventory Decision Platform."""
import os
import textwrap
import importlib
import streamlit as st

import models.persistence
import core.decision_persistence
import core.product_matcher
import core.voice_inventory
import core.gemini_inventory_vision
import core.inventory_reconciliation
import core.billing.subscription_service

importlib.reload(models.persistence)
importlib.reload(core.decision_persistence)
importlib.reload(core.product_matcher)
importlib.reload(core.voice_inventory)
importlib.reload(core.gemini_inventory_vision)
importlib.reload(core.inventory_reconciliation)
importlib.reload(core.billing.subscription_service)

import ui.views.auth
import ui.views.dashboard
import ui.views.workbench
import ui.views.inventory_capture
import ui.views.what_if
import ui.views.history
import ui.views.audit
import ui.views.pricing
import ui.views.settings

# Force reload all view modules to ensure Streamlit hot-reloading picks up updated code immediately
importlib.reload(ui.views.auth)
importlib.reload(ui.views.dashboard)
importlib.reload(ui.views.workbench)
importlib.reload(ui.views.inventory_capture)
importlib.reload(ui.views.what_if)
importlib.reload(ui.views.history)
importlib.reload(ui.views.audit)
importlib.reload(ui.views.pricing)
importlib.reload(ui.views.settings)

from database.database import Database
from ui.theme import inject_theme
from ui.components import render_brand_header
from ui.views.auth import (
    get_current_user,
    render_auth_form,
    render_auth_view,
    render_top_right_auth_widget,
)
from ui.views.dashboard import render_dashboard_view
from ui.views.workbench import render_workbench_view
from ui.views.inventory_capture import render_inventory_capture_view
from ui.views.what_if import render_what_if_view
from ui.views.history import render_history_view
from ui.views.audit import render_audit_view
from ui.views.pricing import render_pricing_view
from ui.views.settings import render_settings_view

def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())

def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)

# Page Config & Theme System
st.set_page_config(
    page_title="AgentStock AI | Enterprise Supply Chain Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_theme()

# Initialize SQLite Database Connection
database = Database("agentstock.db")
database.initialize()

# Retrieve Active User (Optional / Non-blocking)
current_user = get_current_user(database)

# Sidebar Brand Header & Navigation Shell
with st.sidebar:
    render_brand_header()
    
    # User Profile / Guest Status Card
    if current_user:
        _h(
            f"""
            <div style="padding: 10px 14px; background: rgba(109, 93, 252, 0.12); border: 1px solid rgba(109, 93, 252, 0.3); border-radius: 14px; margin-bottom: 16px;">
                <div style="font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: 0.08em;">
                    ACTIVE USER
                </div>
                <div style="font-size: 14px; font-weight: 800; color: #FFFFFF; margin-top: 2px;">
                    👤 {current_user.name}
                </div>
                <div style="font-size: 11px; color: #4ADE80; font-weight: 600; margin-top: 2px;">
                    ✓ Verified Account ({current_user.email})
                </div>
            </div>
            """
        )
    else:
        _h(
            """
            <div style="padding: 10px 14px; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border); border-radius: 14px; margin-bottom: 16px;">
                <div style="font-size: 11px; font-weight: 700; color: #F59E0B; text-transform: uppercase; letter-spacing: 0.08em;">
                    WORKSPACE MODE
                </div>
                <div style="font-size: 14px; font-weight: 800; color: #FFFFFF; margin-top: 2px;">
                    👤 Guest Visitor
                </div>
                <div style="font-size: 11px; color: var(--muted); font-weight: 500; margin-top: 2px;">
                    Exploring Workspace • Sign In Available
                </div>
            </div>
            """
        )
    
    # Navigation Radio Selector
    nav_options = [
        "📊 Dashboard",
        "⚡ Smart Inventory Capture",
        "⚡ Decision Workbench",
        "🔮 What-If Analysis",
        "📜 Decision History",
        "🛡️ Audit Trail",
        "💎 SaaS Pricing",
        "⚙️ Settings & Catalog",
    ]
    
    # Handle programmatic button navigation
    if "pending_nav_page" in st.session_state and st.session_state["pending_nav_page"] in nav_options:
        st.session_state["app_sidebar_nav_radio"] = st.session_state.pop("pending_nav_page")
    elif "app_sidebar_nav_radio" not in st.session_state or st.session_state["app_sidebar_nav_radio"] not in nav_options:
        st.session_state["app_sidebar_nav_radio"] = "📊 Dashboard"

    selected_page = st.radio(
        "NAVIGATION",
        nav_options,
        key="app_sidebar_nav_radio"
    )
    st.session_state["nav_page"] = selected_page

    st.divider()

    # Sidebar Quick Stats & AI Status
    _h(
        """
        <div style="padding: 12px 14px; background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: 14px; margin-bottom: 12px;">
            <div style="font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em;">
                GOOGLE GEMINI CHALLENGE
            </div>
            <div style="font-size: 13px; font-weight: 700; color: #FFFFFF; margin-top: 4px;">
                AgentStock AI v5.0
            </div>
            <div style="font-size: 12px; color: var(--accent); margin-top: 2px;">
                Fact-Bounded AI Decision Engine
            </div>
        </div>
        """
    )

    # API Status
    gemini_active = bool(os.environ.get("GEMINI_API_KEY"))
    status_color = "#4ADE80" if gemini_active else "#FBBF24"
    status_text = "Gemini 3.6 Connected" if gemini_active else "Engine Standalone"
    
    _h(
        f"""
        <div style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); margin-bottom: 16px;">
            <div style="width: 8px; height: 8px; border-radius: 50%; background-color: {status_color};"></div>
            <span>{status_text}</span>
        </div>
        """
    )

    # Sidebar Auth Controls
    if current_user:
        if st.button("🚪 Sign Out"):
            st.session_state["is_logged_in"] = False
            st.session_state["authenticated_user"] = None
            st.session_state["pending_otp_email"] = None
            st.rerun()
    else:
        with st.popover("🔑 Sign In / Register", icon="🔑", key="sb_auth_popover"):
            render_auth_form(database, key_prefix="sb_auth_pop")

# Top-Level Global OTP Verification Banner (if registration in progress)
if st.session_state.get("pending_otp_email"):
    pending_em = st.session_state["pending_otp_email"]
    active_otp = database.get_otp(pending_em)
    _h(
        f"""
        <div style="background: linear-gradient(135deg, rgba(109, 93, 252, 0.25), rgba(0, 212, 255, 0.2)); border: 1.5px solid #6D5DFC; border-radius: 16px; padding: 18px 22px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div>
                    <div style="font-size: 11px; font-weight: 800; color: #00D4FF; letter-spacing: 0.1em; text-transform: uppercase;">
                        🔒 EMAIL OTP VERIFICATION REQUIRED
                    </div>
                    <div style="font-size: 17px; font-weight: 700; color: #FFFFFF; margin-top: 2px;">
                        Complete Registration for <span style="color: #00D4FF;">{pending_em}</span>
                    </div>
                </div>
                <div style="background: rgba(0, 0, 0, 0.4); border: 1px solid rgba(0, 212, 255, 0.5); padding: 6px 16px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 10px; color: var(--muted); text-transform: uppercase; font-weight: 700;">CHALLENGE OTP CODE</div>
                    <div style="font-size: 22px; font-weight: 800; color: #00D4FF; letter-spacing: 0.2em;">{active_otp}</div>
                </div>
            </div>
        </div>
        """
    )
    col_v, col_c, _ = st.columns([1.8, 1, 3])
    with col_v:
        if st.button("⚡ 1-Click Auto-Fill & Verify OTP", type="primary", key="global_otp_autofill"):
            database.verify_user(pending_em)
            database.delete_otp(pending_em)
            u = database.get_user_by_email(pending_em)
            if u:
                st.session_state["is_logged_in"] = True
                st.session_state["authenticated_user"] = u
                st.session_state["pending_otp_email"] = None
                st.success(f"✓ Welcome {u.name}! Email verified successfully.")
                st.rerun()
    with col_c:
        if st.button("Cancel / Dismiss", key="global_otp_cancel"):
            st.session_state["pending_otp_email"] = None
            st.rerun()
    st.divider()

# Main Application Router
if selected_page == "📊 Dashboard":
    render_dashboard_view(database)
elif selected_page == "⚡ Smart Inventory Capture":
    render_inventory_capture_view(database)
elif selected_page == "⚡ Decision Workbench":
    render_workbench_view(database)
elif selected_page == "🔮 What-If Analysis":
    render_what_if_view(database)
elif selected_page == "📜 Decision History":
    render_history_view(database)
elif selected_page == "🛡️ Audit Trail":
    render_audit_view(database)
elif selected_page == "💎 SaaS Pricing":
    render_pricing_view(database)
elif selected_page == "⚙️ Settings & Catalog":
    render_settings_view(database)