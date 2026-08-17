"""AgentStock AI — Enterprise AI Inventory Intelligence & Decision Platform."""
import os
import importlib
import logging
import re
import sys
import traceback
from datetime import datetime, timezone
from uuid import uuid4
import streamlit as st

import models.persistence
import core.decision_persistence
import core.product_matcher
import core.voice_inventory
import core.gemini_inventory_vision
import core.inventory_reconciliation
import core.billing.subscription_service
import core.billing.razorpay_service
import core.billing.coupon_service
import core.supplier_communication
import core.document_processor
import core.chatbot
import core.security
import core.config

# Reload configuration before importing views so newly added config helpers are
# available during Streamlit's in-process hot reload.
importlib.reload(core.config)

import ui.views.auth
import ui.views.landing
import ui.views.dashboard
import ui.views.workbench
import ui.views.inventory_capture
import ui.views.suppliers
import ui.views.documents
import ui.views.what_if
import ui.views.history
import ui.views.audit
import ui.views.pricing
import ui.views.settings
import ui.views.admin
import ui.views.legal
import ui.views.onboarding

# Force reload view modules for seamless live hot-reloading
importlib.reload(ui.views.auth)
importlib.reload(ui.views.landing)
importlib.reload(ui.views.dashboard)
importlib.reload(ui.views.workbench)
importlib.reload(ui.views.inventory_capture)
importlib.reload(ui.views.suppliers)
importlib.reload(ui.views.documents)
importlib.reload(ui.views.what_if)
importlib.reload(ui.views.history)
importlib.reload(ui.views.audit)
importlib.reload(ui.views.pricing)
importlib.reload(ui.views.settings)
importlib.reload(ui.views.admin)
importlib.reload(ui.views.legal)
importlib.reload(ui.views.onboarding)

from database.database import Database
from ui.theme import inject_theme
from ui.components import render_brand_header
from ui.views.auth import (
    get_current_user,
    render_auth_form,
    render_auth_view,
    render_top_right_auth_widget,
    synchronize_google_oidc_user,
    clear_user_scoped_session_state,
)
from ui.views.landing import render_landing_page
from ui.views.dashboard import render_dashboard_view
from ui.views.workbench import render_workbench_view
from ui.views.inventory_capture import render_inventory_capture_view
from ui.views.suppliers import render_suppliers_view
from ui.views.documents import render_documents_view
from ui.views.what_if import render_what_if_view
from ui.views.history import render_history_view
from ui.views.audit import render_audit_view
from ui.views.pricing import render_pricing_view
from ui.views.settings import render_settings_view
from ui.views.admin import render_admin_dashboard
from ui.views.legal import render_legal_view
from ui.views.onboarding import render_onboarding_view
from core.config import get_gemini_api_key
from core.billing.subscription_service import SubscriptionService
from core.security import require_authenticated_user, require_active_subscription, require_admin

logger = logging.getLogger("agentstock")


def _redact_error_detail(value: str) -> str:
    """Avoid exposing credential-like values in developer diagnostics."""
    value = re.sub(
        r"(?i)(password|secret|token|api[_-]?key|credential)\s*([=:])\s*[^\s,;]+",
        r"\1\2 [REDACTED]",
        value,
    )
    return re.sub(r"(://)[^\s/@:]+:[^\s/@]+@", r"\1[REDACTED]@", value)


def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())


def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


# 1. Page Config & Enterprise CSS Theme
st.set_page_config(
    page_title="AgentStock AI | AI-Powered Inventory Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()

# 2. Initialize Multi-Tenant Database
database = Database("agentstock.db")
database.initialize()

# 3. Resolve Current Authenticated User & Subscription Status
current_user = synchronize_google_oidc_user(database) or get_current_user(database)
sub_service = SubscriptionService(database)
user_id = current_user.id if current_user else None
user_subscription = sub_service.get_user_subscription(user_id) if user_id else None
is_subscribed = sub_service.is_subscription_active(user_id) if user_id else False

is_admin_user, _ = require_admin(current_user)

# 4. Sidebar Brand Header & Dynamic Navigation
with st.sidebar:
    render_brand_header()

    # User Status Card
    if current_user:
        if is_admin_user:
            role_label = "👑 Platform Administrator"
            tag_color = "#F59E0B"
        elif is_subscribed:
            plan_name = user_subscription.plan_name.upper() if user_subscription else "ACTIVE"
            role_label = f"⚡ {plan_name} Plan"
            tag_color = "#6D5DFC"
        else:
            role_label = "⏳ Subscription Inactive"
            tag_color = "#EF4444"

        _h(
            f"""
            <div style="padding: 10px 14px; background: rgba(109, 93, 252, 0.12); border: 1px solid rgba(109, 93, 252, 0.35); border-radius: 14px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-size: 10px; font-weight: 800; color: {tag_color}; text-transform: uppercase; letter-spacing: 0.08em;">
                        {role_label}
                    </div>
                </div>
                <div style="font-size: 14px; font-weight: 800; color: #FFFFFF; margin-top: 2px;">
                    👤 {current_user.name}
                </div>
                <div style="font-size: 11px; color: #4ADE80; font-weight: 600; margin-top: 2px;">
                    ✓ {current_user.email}
                </div>
            </div>
            """
        )
    else:
        if st.session_state.pop("google_oauth_error", None):
            st.error("Google sign-in was not completed. Please try again.")
        _h(
            """
            <div style="padding: 10px 14px; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border); border-radius: 14px; margin-bottom: 16px;">
                <div style="font-size: 11px; font-weight: 700; color: #00D4FF; text-transform: uppercase; letter-spacing: 0.08em;">
                    WELCOME
                </div>
                <div style="font-size: 13px; color: var(--muted); margin-top: 2px;">
                    Sign in to access your inventory workspace.
                </div>
            </div>
            """
        )

    # Dynamic Navigation options based on auth and subscription state
    if not current_user:
        nav_options = [
            "🏠 Welcome to AgentStock AI",
            "💎 SaaS Pricing",
            "⚖️ Legal & Privacy (GDPR)",
            "🔑 Sign In / Register",
        ]
        default_nav = "🏠 Welcome to AgentStock AI"
    else:
        # Authenticated User (Allows exploring all tools; operational commits gated in-view)
        nav_options = [
            "📊 Workspace Dashboard",
            "⚡ Smart Inventory Capture",
            "🚚 Supplier Directory & POs",
            "📄 Invoice & Doc OCR",
            "⚡ Decision Workbench",
            "🔮 What-If Simulator",
            "📜 Decision History",
            "💎 SaaS Pricing",
            "🚀 12-Step Guided Tour",
            "⚙️ Settings & Catalog",
            "⚖️ Legal & Privacy (GDPR)",
        ]
        if is_admin_user:
            nav_options.append("🛡️ Audit Trail")
            nav_options.append("👑 Platform Superadmin")
        default_nav = "📊 Workspace Dashboard"

    # Navigation State Resolver
    if "pending_nav_page" in st.session_state and st.session_state["pending_nav_page"] in nav_options:
        st.session_state["app_sidebar_nav_radio"] = st.session_state.pop("pending_nav_page")
    elif "selected_nav_page" in st.session_state and st.session_state["selected_nav_page"] in nav_options:
        st.session_state["app_sidebar_nav_radio"] = st.session_state.pop("selected_nav_page")
    elif "app_sidebar_nav_radio" not in st.session_state or st.session_state["app_sidebar_nav_radio"] not in nav_options:
        st.session_state["app_sidebar_nav_radio"] = default_nav

    selected_page = st.radio(
        "WORKSPACE NAVIGATION",
        nav_options,
        key="app_sidebar_nav_radio",
    )
    st.session_state["nav_page"] = selected_page

    st.divider()

    # Engine Status
    gemini_key = get_gemini_api_key()
    status_color = "#4ADE80" if gemini_key else "#FBBF24"
    status_text = "Gemini Multimodal Active" if gemini_key else "Deterministic Engine"

    _h(
        f"""
        <div style="padding: 12px 14px; background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: 14px; margin-bottom: 12px;">
            <div style="font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em;">
                SYSTEM STATE
            </div>
            <div style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #CBD5E1; margin-top: 4px;">
                <div style="width: 8px; height: 8px; border-radius: 50%; background-color: {status_color};"></div>
                <span>{status_text}</span>
            </div>
        </div>
        """
    )

    # Auth Sign Out / Sign In Action
    if current_user:
        if st.button("🚪 Sign Out", key="sb_btn_signout", width="stretch"):
            if st.session_state.get("auth_provider") == "google":
                st.logout()
            st.session_state["is_logged_in"] = False
            st.session_state["authenticated_user"] = None
            st.session_state["is_admin"] = False
            clear_user_scoped_session_state()
            st.session_state.pop("auth_provider", None)
            st.session_state["pending_otp_email"] = None
            st.rerun()
    else:
        with st.popover("🔑 Sign In / Register", icon="🔑", key="sb_auth_popover"):
            render_auth_form(database, key_prefix="sb_auth_pop")


# 5. Protected View Helper
def _render_subscription_required():
    """Render professional subscription-required screen for inactive subscribers."""
    _h(
        """
        <div style="max-width: 800px; margin: 30px auto 20px auto; text-align: center;">
            <div style="font-size: 42px; margin-bottom: 8px;">💎</div>
            <h1 style="font-size: 32px; font-weight: 800; color: #FFFFFF; margin: 0;">
                Subscription Required
            </h1>
            <p style="font-size: 16px; color: var(--muted); margin: 10px auto 24px auto; max-width: 600px; line-height: 1.6;">
                An active subscription plan is required to access your business workspace, inventory scanner, purchase order dispatcher, and AI decision models.
            </p>
        </div>
        """
    )
    render_pricing_view(database)


# 6. Global Main Router with Error Boundary
try:
    if selected_page == "🏠 Welcome to AgentStock AI":
        render_landing_page(database)

    elif selected_page in ["🔑 Sign In / Register", "🔑 Sign In"]:
        render_auth_view(database)

    elif selected_page == "💎 SaaS Pricing":
        render_pricing_view(database)

    elif selected_page == "💳 Activate Subscription":
        _render_subscription_required()

    elif selected_page == "⚖️ Legal & Privacy (GDPR)":
        render_legal_view(database)

    elif selected_page == "🛡️ Audit Trail":
        # Defense in depth: this remains protected even if a caller attempts
        # to set navigation state outside the sidebar options.
        auth_ok, msg = require_admin(current_user)
        if auth_ok:
            render_audit_view(database)
        else:
            st.error(msg)

    # Workspace Routes (Require Authenticated User; Operational Tools Gated In-View)
    elif selected_page in [
        "📊 Workspace Dashboard",
        "⚡ Smart Inventory Capture",
        "🚚 Supplier Directory & POs",
        "📄 Invoice & Doc OCR",
        "⚡ Decision Workbench",
        "🔮 What-If Simulator",
        "📜 Decision History",
        "🚀 12-Step Guided Tour",
        "⚙️ Settings & Catalog",
        "⚙️ Profile Settings",
    ]:
        # Server-side authentication check
        if not current_user:
            st.warning("🔒 Please sign in to access your business workspace.")
            render_auth_view(database)
        else:
            # Workspace View Execution (In-view checks gate operational commits if unsubscribed)
            if selected_page == "📊 Workspace Dashboard":
                render_dashboard_view(database)
            elif selected_page == "⚡ Smart Inventory Capture":
                render_inventory_capture_view(database)
            elif selected_page == "🚚 Supplier Directory & POs":
                render_suppliers_view(database)
            elif selected_page == "📄 Invoice & Doc OCR":
                render_documents_view(database)
            elif selected_page == "⚡ Decision Workbench":
                render_workbench_view(database)
            elif selected_page == "🔮 What-If Simulator":
                render_what_if_view(database)
            elif selected_page == "📜 Decision History":
                render_history_view(database)
            elif selected_page == "🚀 12-Step Guided Tour":
                render_onboarding_view(database)
            elif selected_page in ["⚙️ Settings & Catalog", "⚙️ Profile Settings"]:
                render_settings_view(database)

    elif selected_page == "👑 Platform Superadmin":
        auth_ok, msg = require_admin(current_user)
        if auth_ok:
            render_admin_dashboard(database)
        else:
            st.error(msg)

except Exception as err:
    from core.config import get_app_env

    error_ref_id = f"ERR-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:8].upper()}"
    app_env = get_app_env()
    traceback_text = _redact_error_detail("".join(traceback.format_exception(type(err), err, err.__traceback__)))

    # Log error server-side with unique reference ID
    logger.error("[%s] Unhandled exception during page rendering", error_ref_id, exc_info=True)

    if app_env != "production":
        # Print complete traceback to terminal in development/local
        sys.stderr.write(f"\n[AGENTSTOCK ERROR - {error_ref_id}]\n")
        sys.stderr.write(traceback_text)
        sys.stderr.flush()

    _h(
        f"""
        <div style="background: rgba(239, 68, 68, 0.12); border: 1.5px solid #EF4444; border-radius: 14px; padding: 28px; text-align: center; max-width: 680px; margin: 40px auto 20px auto;">
            <div style="font-size: 40px; margin-bottom: 10px;">⚠️</div>
            <div style="font-size: 22px; font-weight: 800; color: #FFFFFF;">Something went wrong</div>
            <div style="font-size: 14px; color: #CBD5E1; margin: 8px auto 14px auto; max-width: 520px; line-height: 1.6;">
                An unexpected issue occurred while loading this view. Your business data is completely safe.
            </div>
            <div style="display: inline-block; background: rgba(0, 0, 0, 0.35); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 6px 14px; font-family: monospace; font-size: 12px; color: #FCA5A5;">
                Reference ID: {error_ref_id}
            </div>
        </div>
        """
    )

    if app_env != "production":
        # Developer-only expandable diagnostic panel
        exc_type = type(err).__name__
        exc_msg = _redact_error_detail(str(err))
        tb_list = traceback.extract_tb(err.__traceback__)
        last_frame = tb_list[-1] if tb_list else None
        f_name = last_frame.filename if last_frame else "Unknown"
        line_no = last_frame.lineno if last_frame else "Unknown"
        function_name = last_frame.name if last_frame else "Unknown"

        with st.expander(f"🛠️ Developer Diagnostics [{exc_type}] — (APP_ENV={app_env})", expanded=True):
            st.markdown(f"**Exception Type:** `{exc_type}`")
            st.markdown(f"**Message:** `{exc_msg}`")
            st.markdown(f"**File:** `{f_name}` (Line `{line_no}`)")
            st.markdown(f"**Function:** `{function_name}`")
            st.code(traceback_text, language="python")

    c_err1, c_err2 = st.columns([1, 1])
    with c_err1:
        if st.button("🔄 Refresh Page", type="primary", key="err_refresh_btn", width="stretch"):
            st.rerun()
    with c_err2:
        if st.button("🏠 Return to Welcome", key="err_home_btn", width="stretch"):
            st.session_state["pending_nav_page"] = "🏠 Welcome to AgentStock AI"
            st.rerun()
