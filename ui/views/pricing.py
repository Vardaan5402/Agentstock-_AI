import os
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import streamlit as st
from database.database import Database
from models.subscription import UserSubscription, SubscriptionStatus, PlanTier
from core.billing.stripe_service import StripeBillingService
from core.billing.subscription_service import SubscriptionService
from ui.views.auth import get_current_user
from ui.components import render_section_header, render_pricing_card

def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())

def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)

def render_pricing_view(database: Database):
    """Render the SaaS Pricing & Subscription view with Stripe integration."""
    billing_svc = StripeBillingService()
    sub_svc = SubscriptionService(database)
    user = get_current_user(database)

    # 1. Handle Stripe Redirect Query Parameters
    params = st.query_params
    if params.get("checkout_status") == "success":
        plan_param = params.get("plan", "Plan").upper()
        mock_mode = params.get("mock") == "true"
        st.success(f"🎉 **Payment Succeeded!** Your {plan_param} subscription is now active with full enterprise features.")
        if user:
            # Activate in SQLite
            sub = UserSubscription(
                id=uuid4().hex,
                user_id=user.id,
                stripe_customer_id="cus_test_active",
                stripe_subscription_id="sub_test_active",
                plan_name=plan_param,
                subscription_status=SubscriptionStatus.ACTIVE.value,
                current_period_start=datetime.now(timezone.utc).isoformat(),
                current_period_end=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            database.save_subscription(sub)
    elif params.get("checkout_status") == "cancel":
        st.warning("⚠️ Checkout was cancelled. No charges were made. You can resume checkout anytime.")

    # 2. Header
    _h(
        """
        <div style="text-align: center; max-width: 800px; margin: 0 auto 28px auto;">
            <div style="font-size: 12px; font-weight: 800; color: var(--accent); letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 8px;">
                🚀 GOOGLE GEMINI CHALLENGE — SPECIAL LAUNCH PRICING
            </div>
            <h1 style="font-size: 38px; font-weight: 800; letter-spacing: -0.03em; margin: 0; color: #FFFFFF;">
                Democratized AI Supply Chain Intelligence
            </h1>
            <div style="font-size: 16px; color: var(--muted); margin-top: 10px;">
                High-performance inventory decision support at hyper-competitive SMB & D2C pricing.
            </div>
        </div>
        """
    )

    # 3. Active Subscription Card (if user has active paid subscription)
    user_id = user.id if user else None
    current_sub = sub_svc.get_user_subscription(user_id) if user_id else None
    current_plan = current_sub.plan_name.upper() if current_sub else PlanTier.FREE.value

    if current_sub and current_sub.is_active and current_plan != PlanTier.FREE.value:
        col_act1, col_act2 = st.columns([2.5, 1])
        with col_act1:
            _h(
                f"""
                <div class="agent-card" style="border: 2px solid var(--accent); margin-bottom: 24px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-size: 11px; color: var(--accent); font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;">
                                CURRENT ACTIVE SUBSCRIPTION
                            </div>
                            <div style="font-size: 22px; font-weight: 800; color: #FFFFFF; margin-top: 2px;">
                                ⚡ {current_plan} Plan Active
                            </div>
                        </div>
                        <div style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; color: #22C55E; background: rgba(34, 197, 94, 0.12); padding: 5px 12px; border-radius: 20px; border: 1px solid rgba(34, 197, 94, 0.3);">
                            <span>✓ Auto-Renew Active</span>
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255, 255, 255, 0.06); font-size: 13px;">
                        <div><span style="color:var(--muted);">Billing Cycle:</span><br/><strong style="color:#FFF;">Monthly / Annual</strong></div>
                        <div><span style="color:var(--muted);">Renewal Date:</span><br/><strong style="color:#FFF;">30 Days from start</strong></div>
                        <div><span style="color:var(--muted);">Payment Method:</span><br/><strong style="color:#FFF;">Stripe Encrypted Card</strong></div>
                    </div>
                </div>
                """
            )
        with col_act2:
            st.write("")
            st.write("")
            if st.button("💳 Manage in Stripe Portal", key="btn_open_customer_portal", type="secondary"):
                if current_sub.stripe_customer_id:
                    portal = billing_svc.create_customer_portal_session(current_sub.stripe_customer_id)
                    st.link_button("🔗 Open Stripe Customer Portal", portal["url"])
                else:
                    st.info("ℹ️ Test subscription managed locally in SQLite database.")

    # 4. Special Launch Offer Banner
    st.info("💡 **Special Launch Offer**: 50% OFF all plans during the Google Gemini AI Challenge window!")

    # 5. Billing Toggle (Monthly / Yearly)
    col_toggle, _ = st.columns([1.2, 2])
    with col_toggle:
        billing_cycle = st.segmented_control(
            "Billing Cycle",
            ["Monthly Billing", "Yearly Billing (20% Extra OFF)"],
            default="Monthly Billing",
            key="pricing_billing_toggle"
        )

    is_yearly = "Yearly" in (billing_cycle or "Monthly")

    starter_price = "$15" if is_yearly else "$19"
    pro_price = "$39" if is_yearly else "$49"
    enterprise_price = "$119" if is_yearly else "$149"
    period_str = "/ month" if not is_yearly else "/ month (billed annually)"

    # 6. Pricing Cards Grid
    p1, p2, p3 = st.columns(3)

    with p1:
        render_pricing_card(
            title="STARTER",
            price=starter_price,
            period=period_str,
            description="For small retail stores & D2C sellers",
            features=[
                "1 Business Location",
                "Up to 500 AI Decisions / mo",
                "Standard Inventory Simulation",
                "Fact-Bounded Gemini Copilot",
                "WhatsApp & Call PO Dispatch",
                "SQLite Data Storage"
            ],
            is_popular=False,
            button_text="Subscribe to Starter" if current_plan != "STARTER" else "✓ Current Plan",
            key="p_btn_starter"
        )
        if st.session_state.get("p_btn_starter"):
            _initiate_checkout("STARTER", is_yearly, user, billing_svc, database)

    with p2:
        render_pricing_card(
            title="PROFESSIONAL",
            price=pro_price,
            period=period_str,
            description="For growing brands & multi-supplier networks",
            features=[
                "Unlimited Business Locations",
                "Unlimited AI Decisions",
                "Advanced What-If Counterfactuals",
                "Fact Reference & Policy Validation",
                "1-Click Calling & WhatsApp PO Suite",
                "Export Audit Logs to JSON/CSV",
                "Priority 24/7 Agent Support"
            ],
            is_popular=True,
            button_text="Upgrade to Professional" if current_plan != "PROFESSIONAL" else "✓ Current Plan",
            key="p_btn_pro"
        )
        if st.session_state.get("p_btn_pro"):
            _initiate_checkout("PROFESSIONAL", is_yearly, user, billing_svc, database)

    with p3:
        render_pricing_card(
            title="ENTERPRISE",
            price=enterprise_price,
            period=period_str,
            description="For large enterprise supply networks",
            features=[
                "Dedicated Private Cloud / On-Prem",
                "Custom Fine-Tuned Gemini LLM",
                "Single Sign-On (SAML / SSO)",
                "Custom Policy Rules Engine",
                "Direct ERP & WhatsApp Automation",
                "SLA & Dedicated Account Manager"
            ],
            is_popular=False,
            button_text="Subscribe to Enterprise" if current_plan != "ENTERPRISE" else "✓ Current Plan",
            key="p_btn_enterprise"
        )
        if st.session_state.get("p_btn_enterprise"):
            _initiate_checkout("ENTERPRISE", is_yearly, user, billing_svc, database)

    _h("<div style='height: 35px;'></div>")

    # 7. Plan Feature Matrix Table
    render_section_header("Plan Feature Matrix", "Detailed breakdown of capabilities by subscription tier", "📋")

    matrix_data = [
        {"Capability": "Deterministic Inventory Simulation", "Starter": "✓ Included", "Professional": "✓ Included", "Enterprise": "✓ Included"},
        {"Capability": "Gemini 3.6 Structured Reasoning", "Starter": "✓ 500/mo", "Professional": "✓ Unlimited", "Enterprise": "✓ Custom Model"},
        {"Capability": "1-Click Calling & WhatsApp PO Suite", "Starter": "✓ Included", "Professional": "✓ Included", "Enterprise": "✓ Included"},
        {"Capability": "Fact Reference Validation Engine", "Starter": "✓ Included", "Professional": "✓ Included", "Enterprise": "✓ Included"},
        {"Capability": "What-If Counterfactual Analysis", "Starter": "Basic", "Professional": "✓ Advanced", "Enterprise": "✓ Custom Shocks"},
        {"Capability": "Immutable Audit Trail & SQLite History", "Starter": "7 Days", "Professional": "✓ Unlimited", "Enterprise": "✓ Unlimited"},
        {"Capability": "Human Approval Workflow Controls", "Starter": "✓ Included", "Professional": "✓ Included", "Enterprise": "✓ Custom Roles"},
        {"Capability": "Dedicated Customer Support", "Starter": "Email", "Professional": "Priority 24/7", "Enterprise": "Dedicated Manager"},
    ]

    st.dataframe(matrix_data, hide_index=True)

    _h("<div style='height: 25px;'></div>")

    # 8. FAQ Section
    render_section_header("Frequently Asked Questions", "Everything you need to know about AgentStock AI subscriptions", "❓")

    with st.expander("How does Stripe billing and payment security work?", expanded=True):
        st.markdown(
            "All transactions are securely handled by **Stripe Checkout** with end-to-end 256-bit SSL encryption. AgentStock AI never stores your credit card numbers or sensitive payment credentials."
        )

    with st.expander("Can I switch between monthly and yearly billing?"):
        st.markdown(
            "Yes! You can switch or cancel your subscription at any time using the Stripe Customer Portal."
        )

    with st.expander("How does AgentStock AI prevent LLM hallucinations in financial decisions?"):
        st.markdown(
            "AgentStock AI uses a **Fact-Bounded AI Architecture**. All numerical calculations are executed deterministically in Python. Gemini receives this immutable snapshot and is fact-bounded."
        )


def _initiate_checkout(plan_name: str, is_yearly: bool, user, billing_svc: StripeBillingService, database: Database):
    """Execute Stripe Checkout or instant sandbox activation."""
    if not user:
        st.error("Please sign in or create an account to activate a subscription.")
        return

    try:
        session = billing_svc.create_checkout_session(
            user_id=user.id,
            user_email=user.email,
            plan_name=plan_name,
            is_yearly=is_yearly,
        )

        if session.get("mode") == "live":
            st.success(f"✓ Checkout session created! Redirecting to Stripe...")
            st.link_button(f"👉 Proceed to Stripe Checkout for {plan_name}", session["url"], type="primary")
        else:
            # Test sandbox instant activation
            sub = UserSubscription(
                id=uuid4().hex,
                user_id=user.id,
                stripe_customer_id="cus_test_sandbox",
                stripe_subscription_id="sub_test_sandbox",
                stripe_price_id=session.get("price_id"),
                plan_name=plan_name.upper(),
                subscription_status=SubscriptionStatus.ACTIVE.value,
                current_period_start=datetime.now(timezone.utc).isoformat(),
                current_period_end=(datetime.now(timezone.utc) + timedelta(days=365 if is_yearly else 30)).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            database.save_subscription(sub)
            st.success(f"🎉 **{plan_name.upper()} Plan Activated!** (Test Mode Sandbox). You now have full subscription features.")
            st.rerun()
    except Exception as err:
        st.error(f"Payment could not be started: {err}")
