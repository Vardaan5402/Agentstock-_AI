"""SaaS Pricing & Razorpay Subscription Checkout View."""
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import streamlit as st

from database.database import Database
from models.subscription import UserSubscription, SubscriptionStatus, PlanTier, BillingCycle
from core.billing.razorpay_service import RazorpayBillingService
from core.billing.coupon_service import CouponService
from core.billing.subscription_service import SubscriptionService
from ui.views.auth import get_current_user
from ui.components import render_section_header, render_pricing_card
from core.config import format_usd, get_plan_pricing


RAZORPAY_CHECKOUT_SCRIPT = "https://checkout.razorpay.com/v1/checkout.js"


# This is deliberately a Streamlit v2 component, rather than the legacy
# ``components.html`` iframe. Razorpay Checkout is a page-level modal, and an
# iframe can be unmounted by a Streamlit rerun while that modal is open.
# ``setTriggerValue`` returns only the Razorpay response to Python; the plan
# and billing details used for entitlement remain in server-side session state.
_RAZORPAY_CHECKOUT_COMPONENT = st.components.v2.component(
    "agentstock_razorpay_checkout",
    html="""
        <button id="razorpay-checkout-button" type="button">Continue to secure payment</button>
        <div id="razorpay-checkout-status" role="status"></div>
    """,
    css="""
        #razorpay-checkout-button {
            width: 100%; padding: 10px 14px; border: 0; border-radius: 8px;
            background: #7C3AED; color: #fff; font-weight: 700; cursor: pointer;
        }
        #razorpay-checkout-button:disabled { cursor: wait; opacity: 0.75; }
        #razorpay-checkout-status { margin-top: 8px; color: #94A3B8; font: 13px sans-serif; }
    """,
    js="""
        function loadRazorpay(scriptUrl) {
            if (window.Razorpay) {
                return Promise.resolve();
            }
            if (window.__agentstockRazorpayLoadPromise) {
                return window.__agentstockRazorpayLoadPromise;
            }

            window.__agentstockRazorpayLoadPromise = new Promise((resolve, reject) => {
                const script = document.createElement("script");
                script.src = scriptUrl;
                script.async = true;
                script.onload = () => window.Razorpay ? resolve() : reject(new Error("Razorpay did not initialise"));
                script.onerror = () => reject(new Error("Razorpay Checkout could not be loaded"));
                document.head.appendChild(script);
            });
            return window.__agentstockRazorpayLoadPromise;
        }

        export default function(component) {
            const { data, parentElement, setTriggerValue } = component;
            const button = parentElement.querySelector("#razorpay-checkout-button");
            const status = parentElement.querySelector("#razorpay-checkout-status");

            button.onclick = async () => {
                button.disabled = true;
                button.textContent = "Opening secure payment…";
                status.textContent = "";

                try {
                    await loadRazorpay(data.checkout_script);
                    const options = { ...data.options };
                    options.handler = (response) => {
                        status.textContent = "Payment successful. Verifying payment securely…";
                        setTriggerValue("payment", {
                            razorpay_order_id: response.razorpay_order_id,
                            razorpay_payment_id: response.razorpay_payment_id,
                            razorpay_signature: response.razorpay_signature,
                            plan: data.plan_name,
                            is_yearly: data.is_yearly,
                            discount_amount: data.discount_amount,
                            checkout_token: data.checkout_token,
                        });
                    };
                    options.modal = {
                        ondismiss: () => {
                            button.disabled = false;
                            button.textContent = "Continue to secure payment";
                            status.textContent = "Payment was not completed. Your plan remains inactive.";
                        },
                    };

                    const rzp = new window.Razorpay(options);
                    rzp.on("payment.failed", (response) => {
                        const reason = response && response.error && response.error.description
                            ? response.error.description
                            : "Payment was not completed.";
                        setTriggerValue("failed", {
                            reason,
                            checkout_token: data.checkout_token,
                        });
                        button.disabled = false;
                        button.textContent = "Continue to secure payment";
                        status.textContent = reason;
                    });
                    rzp.open();
                } catch (error) {
                    const message = error && error.message
                        ? error.message
                        : "Secure payment could not be opened. Please try again.";
                    status.textContent = message;
                    button.disabled = false;
                    button.textContent = "Continue to secure payment";
                    setTriggerValue("failed", {
                        reason: message,
                        checkout_token: data.checkout_token,
                    });
                }
            };
        }
    """,
)


def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())


def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


def _checkout_prefill_for_user(user) -> dict[str, str]:
    """Build Checkout prefill exclusively from the authenticated user record."""
    prefill = {
        "name": (getattr(user, "name", "") or "").strip(),
        "email": (getattr(user, "email", "") or "").strip(),
    }
    # Do not infer a contact number from a supplier, business profile, browser
    # state, or application default. Razorpay may collect a number itself when
    # the payment method requires one.
    phone = getattr(user, "phone", None)
    if isinstance(phone, str) and phone.strip():
        prefill["contact"] = phone.strip()
    return prefill


def _activate_verified_payment(
    razorpay_svc: RazorpayBillingService,
    database: Database,
    user,
    plan_name: str,
    is_yearly: bool,
    discount_amount: float,
    order_id: str,
    payment_id: str,
    signature: str,
):
    """Verify the Razorpay payment server-side before granting entitlements."""
    if not user:
        st.error("Please sign in or create an account to activate a subscription.")
        return False

    if not order_id or not payment_id or not signature:
        st.error("Payment verification data is incomplete. The plan was NOT activated.")
        return False

    try:
        st.info("Payment successful. Verifying payment securely…")
        verified = razorpay_svc.verify_payment(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
        )
        if not verified:
            st.error("❌ Razorpay payment verification failed. The plan was NOT activated.")
            return False

        now = datetime.now(timezone.utc)
        existing = database.get_subscription_by_razorpay_id(order_id)
        if existing and existing.user_id != user.id:
            st.error("Payment verification failed. The plan was NOT activated.")
            return False

        # This Checkout flow creates a one-time Razorpay Order, not a Razorpay
        # Subscription. Preserve an existing verified customer/subscription ID
        # when present; never fabricate either identifier from the user ID.
        sub = existing or UserSubscription(
            id=f"sub_{user.id[:10]}_{uuid4().hex[:6]}", user_id=user.id
        )
        sub.razorpay_order_id = order_id
        sub.razorpay_payment_id = payment_id
        sub.plan_name = plan_name.upper()
        sub.billing_cycle = BillingCycle.YEARLY.value if is_yearly else BillingCycle.MONTHLY.value
        sub.subscription_status = SubscriptionStatus.ACTIVE.value
        sub.current_period_start = now.isoformat()
        sub.current_period_end = (now + timedelta(days=365 if is_yearly else 30)).isoformat()
        sub.discount_applied = discount_amount
        sub.updated_at = now.isoformat()
        database.save_subscription(sub)

        st.success(
            f"🎉 **{plan_name.upper()} Plan Activated!** "
            "Razorpay payment was verified successfully."
        )
        return True

    except Exception:
        st.error("Payment verification could not be completed. Your plan was NOT activated.")
        return False


def _handle_razorpay_callback(
    database: Database,
    razorpay_svc: RazorpayBillingService,
    user,
):
    """Process the browser callback only after Razorpay returns a payment response."""
    params = st.query_params
    order_id = params.get("razorpay_order_id")
    payment_id = params.get("razorpay_payment_id")
    signature = params.get("razorpay_signature")
    plan_name = params.get("plan")

    if not (order_id and payment_id and signature and plan_name):
        return

    # The current component callback does not use URL parameters. Retain this
    # fallback only for an in-flight legacy checkout and bind it to the same
    # server-created order/context before considering its signed response.
    pending = st.session_state.get("pending_razorpay_checkout")
    if (
        not pending
        or order_id != pending.get("order_id")
        or plan_name.upper() != pending.get("plan_name")
        or (params.get("yearly", "0") == "1") != pending.get("is_yearly")
    ):
        return

    # Prevent a callback from being processed repeatedly in the same session.
    callback_key = f"{order_id}:{payment_id}:{signature}"
    if st.session_state.get("processed_razorpay_callback") == callback_key:
        return

    st.session_state["processed_razorpay_callback"] = callback_key

    if _activate_verified_payment(
        razorpay_svc=razorpay_svc,
        database=database,
        user=user,
        plan_name=pending["plan_name"],
        is_yearly=pending["is_yearly"],
        discount_amount=pending["discount_amount"],
        order_id=order_id,
        payment_id=payment_id,
        signature=signature,
    ):
        # Remove sensitive payment parameters from the URL after processing.
        st.query_params.clear()
        st.rerun()


def render_pricing_view(database: Database):
    """Render SaaS Pricing and Razorpay subscription checkout view."""
    razorpay_svc = RazorpayBillingService()
    sub_svc = SubscriptionService(database)
    user = get_current_user(database)

    # Process a Razorpay success callback before rendering the normal pricing UI.
    _handle_razorpay_callback(database, razorpay_svc, user)
    pending_checkout = st.session_state.get("pending_razorpay_checkout")
    selected_payment_plan = pending_checkout.get("plan_name") if pending_checkout else None

    # 1. Header
    _h(
        """
        <div style="text-align: center; max-width: 800px; margin: 0 auto 28px auto;">
            <div style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 8px;">
                💎 FLEXIBLE PLANS FOR BUSINESSES
            </div>
            <h1 style="font-size: 36px; font-weight: 800; letter-spacing: -0.03em; margin: 0; color: #FFFFFF;">
                AI Inventory Decision Platform
            </h1>
            <div style="font-size: 15px; color: var(--muted); margin-top: 10px;">
                Predict stockouts, automate supplier communications, and scan physical stock with confidence.
            </div>
        </div>
        """
    )

    # 2. Active Subscription Card (if user has active subscription)
    user_id = user.id if user else None
    current_sub = sub_svc.get_user_subscription(user_id) if user_id else None
    current_plan = current_sub.plan_name.upper() if current_sub else PlanTier.FREE.value

    if current_sub and current_sub.is_active and current_plan != PlanTier.FREE.value:
        usage = sub_svc.get_usage(user_id)
        pricing = get_plan_pricing(current_plan)

        _h(
            f"""
            <div class="agent-card" style="border: 2px solid var(--accent); margin-bottom: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-size: 11px; color: var(--accent); font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;">
                            ACTIVE SUBSCRIPTION
                        </div>
                        <div style="font-size: 22px; font-weight: 800; color: #FFFFFF; margin-top: 2px;">
                            ⚡ {current_plan} Plan Active
                        </div>
                    </div>
                    <div style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; color: #22C55E; background: rgba(34, 197, 94, 0.12); padding: 5px 12px; border-radius: 20px; border: 1px solid rgba(34, 197, 94, 0.3);">
                        <span>✓ Verified via Razorpay</span>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255, 255, 255, 0.06); font-size: 13px;">
                    <div><span style="color:var(--muted);">Camera Scans Used:</span><br/><strong style="color:#FFF;">{usage.camera_scans} / {pricing.get('camera_scans', 100)}</strong></div>
                    <div><span style="color:var(--muted);">Voice Queries Used:</span><br/><strong style="color:#FFF;">{usage.voice_queries} / {pricing.get('voice_queries', 250)}</strong></div>
                    <div><span style="color:var(--muted);">AI Decisions Used:</span><br/><strong style="color:#FFF;">{usage.ai_decisions} / {pricing.get('ai_decisions', 500)}</strong></div>
                    <div><span style="color:var(--muted);">Billing Status:</span><br/><strong style="color:#4ADE80;">Active (Auto-Renew)</strong></div>
                </div>
            </div>
            """
        )

    # 3. Promotional Coupon Entry
    col_coup1, col_coup2 = st.columns([1.5, 1])
    with col_coup1:
        st.info("💡 **Special Offer**: Use coupon code **`LAUNCH50`** for 50% OFF your first subscription period!")

    with col_coup2:
        with st.form("pricing_coupon_form"):
            c_code = st.text_input("Promotional Coupon Code", placeholder="e.g. LAUNCH50", key="coupon_input_code")
            submit_coupon = st.form_submit_button("Apply Code")
            if submit_coupon:
                valid, c_msg, disc_val = CouponService.validate_coupon(c_code, current_plan, user_id)
                if valid:
                    coupon = CouponService.get_coupon(c_code)
                    st.session_state["active_coupon_code"] = c_code.upper()
                    st.session_state["active_coupon_discount"] = disc_val
                    st.session_state["active_coupon_discount_type"] = coupon["discount_type"]
                    discount_label = f"{disc_val:g}% OFF" if coupon["discount_type"] == "PERCENTAGE" else f"{format_usd(disc_val)} OFF"
                    st.success(f"✓ {c_msg} ({discount_label})")
                else:
                    st.error(c_msg)

    # 4. Billing Cycle Selector
    col_toggle, _ = st.columns([1.2, 2])
    with col_toggle:
        billing_cycle = st.segmented_control(
            "Billing Frequency",
            ["Monthly Billing", "Yearly Billing (20% Extra Savings)"],
            default="Monthly Billing",
            key="pricing_billing_toggle"
        )

    is_yearly = "Yearly" in (billing_cycle or "Monthly")
    applied_discount = st.session_state.get("active_coupon_discount", 0.0)
    discount_type = st.session_state.get("active_coupon_discount_type", "PERCENTAGE")

    # Calculate Prices
    st_p = get_plan_pricing("STARTER", is_yearly)
    pr_p = get_plan_pricing("PROFESSIONAL", is_yearly)
    en_p = get_plan_pricing("ENTERPRISE", is_yearly)

    st_rate = st_p["yearly_usd"] if is_yearly else st_p["monthly_usd"]
    pr_rate = pr_p["yearly_usd"] if is_yearly else pr_p["monthly_usd"]
    en_rate = en_p["yearly_usd"] if is_yearly else en_p["monthly_usd"]

    if applied_discount > 0:
        st_rate = CouponService.calculate_discounted_price(st_rate, discount_type, applied_discount)
        pr_rate = CouponService.calculate_discounted_price(pr_rate, discount_type, applied_discount)
        en_rate = CouponService.calculate_discounted_price(en_rate, discount_type, applied_discount)

    period_str = "/ mo (billed annually)" if is_yearly else "/ month"

    # 5. Pricing Grid
    p1, p2, p3 = st.columns(3)

    with p1:
        render_pricing_card(
            title="STARTER",
            price=format_usd(st_rate),
            period=period_str,
            description="For small retail stores & single-location shops",
            features=[
                "1 Business Location",
                f"{st_p['camera_scans']} Camera Scans / mo",
                f"{st_p['voice_queries']} Voice Queries / mo",
                f"{st_p['ai_decisions']} AI Decision Reviews / mo",
                "WhatsApp & Phone PO Dispatch",
                "Standard Email Support",
            ],
            is_popular=False,
            button_text=(
                "✓ Selected — Complete Payment Below"
                if selected_payment_plan == "STARTER"
                else ("Subscribe to Starter" if current_plan != "STARTER" else "✓ Active Plan")
            ),
            key="p_btn_starter",
        )
        if st.session_state.get("p_btn_starter"):
            _initiate_razorpay_checkout("STARTER", is_yearly, applied_discount, discount_type, user, razorpay_svc, database)
        if selected_payment_plan == "STARTER":
            _render_pending_razorpay_checkout(database, razorpay_svc, user, "STARTER")

    with p2:
        render_pricing_card(
            title="PROFESSIONAL",
            price=format_usd(pr_rate),
            period=period_str,
            description="For growing brands & multi-supplier networks",
            features=[
                "Unlimited Business Locations",
                f"{pr_p['camera_scans']:,} Camera Scans / mo",
                f"{pr_p['voice_queries']:,} Voice Queries / mo",
                "Unlimited AI Decision Reviews",
                "What-If Counterfactual Simulator",
                "Document & Invoice OCR",
                "Priority 24/7 Support",
            ],
            is_popular=True,
            button_text=(
                "✓ Selected — Complete Payment Below"
                if selected_payment_plan == "PROFESSIONAL"
                else ("Upgrade to Professional" if current_plan != "PROFESSIONAL" else "✓ Active Plan")
            ),
            key="p_btn_pro",
        )
        if st.session_state.get("p_btn_pro"):
            _initiate_razorpay_checkout("PROFESSIONAL", is_yearly, applied_discount, discount_type, user, razorpay_svc, database)
        if selected_payment_plan == "PROFESSIONAL":
            _render_pending_razorpay_checkout(database, razorpay_svc, user, "PROFESSIONAL")

    with p3:
        render_pricing_card(
            title="ENTERPRISE",
            price=format_usd(en_rate),
            period=period_str,
            description="For high-volume warehouse supply networks",
            features=[
                "Unlimited Everything",
                "Custom Multimodal Models",
                "Direct ERP & WhatsApp Automation",
                "Multi-Tenant RBAC Governance",
                "Dedicated Account Manager",
                "99.9% Uptime SLA",
            ],
            is_popular=False,
            button_text=(
                "✓ Selected — Complete Payment Below"
                if selected_payment_plan == "ENTERPRISE"
                else ("Subscribe to Enterprise" if current_plan != "ENTERPRISE" else "✓ Active Plan")
            ),
            key="p_btn_enterprise",
        )
        if st.session_state.get("p_btn_enterprise"):
            _initiate_razorpay_checkout("ENTERPRISE", is_yearly, applied_discount, discount_type, user, razorpay_svc, database)
        if selected_payment_plan == "ENTERPRISE":
            _render_pending_razorpay_checkout(database, razorpay_svc, user, "ENTERPRISE")

    _h("<div style='height: 35px;'></div>")

    # 6. Plan Feature Matrix
    render_section_header("Plan Feature Matrix", "Detailed breakdown of capabilities by subscription tier", "📋")

    matrix_data = [
        {"Feature / Capability": "Deterministic Risk Engine", "Starter": "✓ Included", "Professional": "✓ Included", "Enterprise": "✓ Included"},
        {"Feature / Capability": "AI Camera Inventory Scanner", "Starter": "100 / mo", "Professional": "1,000 / mo", "Enterprise": "Unlimited"},
        {"Feature / Capability": "Multilingual Voice Assistant", "Starter": "250 / mo", "Professional": "1,500 / mo", "Enterprise": "Unlimited"},
        {"Feature / Capability": "1-Click WhatsApp & Phone POs", "Starter": "✓ Included", "Professional": "✓ Included", "Enterprise": "✓ Included"},
        {"Feature / Capability": "What-If Counterfactual Simulator", "Starter": "Basic", "Professional": "✓ Advanced", "Enterprise": "✓ Custom"},
        {"Feature / Capability": "Document / Invoice OCR", "Starter": "50 / mo", "Professional": "500 / mo", "Enterprise": "Unlimited"},
        {"Feature / Capability": "Immutable Audit Trail", "Starter": "30 Days", "Professional": "✓ Unlimited", "Enterprise": "✓ Unlimited"},
        {"Feature / Capability": "Dedicated Account Support", "Starter": "Standard Email", "Professional": "Priority 24/7", "Enterprise": "Dedicated Manager"},
    ]

    st.dataframe(matrix_data, hide_index=True)


def _initiate_razorpay_checkout(
    plan_name: str,
    is_yearly: bool,
    discount_amount: float,
    discount_type: str,
    user,
    razorpay_svc: RazorpayBillingService,
    database: Database,
):
    """Create a real Razorpay order and retain its checkout context; never activate here."""
    if not user:
        st.error("Please sign in or create an account to activate a subscription.")
        return

    pending = st.session_state.get("pending_razorpay_checkout")
    if pending:
        if pending.get("plan_name") == plan_name.upper():
            st.info("Your secure payment checkout is ready below this plan.")
            return
        # A deliberate choice of another plan replaces only an unpaid local
        # checkout context. No payment or entitlement is created here.
        st.session_state.pop("pending_razorpay_checkout", None)
        st.session_state.pop("shown_razorpay_checkout_failure", None)

    try:
        order = razorpay_svc.create_order(
            user_id=user.id,
            user_email=user.email,
            plan_name=plan_name,
            is_yearly=is_yearly,
            discount_amount=discount_amount,
            discount_type=discount_type,
        )

        if not order.get("id"):
            raise RuntimeError("Razorpay did not return a valid order ID.")

        key_id = razorpay_svc.get_checkout_key_id()
        if not key_id:
            raise RuntimeError(
                "Razorpay credentials are not configured. "
                "The plan was NOT activated."
            )

        # Keep these values in the server session. The browser receives the
        # public Checkout configuration only; it never decides the plan or
        # entitlement that will be activated after a payment response.
        checkout_options = {
            "key": key_id,
            "amount": order["amount"],
            "currency": order["currency"],
            "name": "AgentStock AI",
            "description": f"{plan_name.title()} Plan",
            "order_id": order["id"],
            "prefill": _checkout_prefill_for_user(user),
            "theme": {"color": "#7C3AED"},
        }
        st.session_state["pending_razorpay_checkout"] = {
            "checkout_token": uuid4().hex,
            "order_id": order["id"],
            "plan_name": plan_name.upper(),
            "is_yearly": is_yearly,
            "discount_amount": discount_amount,
            "options": checkout_options,
        }
        # The payment control mounts on the next stable rerun, instead of in
        # the transient rerun that handled the Streamlit Subscribe button.
        st.rerun()

    except Exception:
        st.error("Secure checkout could not be started. Please try again later.")


def _render_pending_razorpay_checkout(
    database: Database,
    razorpay_svc: RazorpayBillingService,
    user,
    plan_name: str,
):
    """Mount the one pending Checkout control beneath its selected plan."""
    pending = st.session_state.get("pending_razorpay_checkout")
    if not pending or pending.get("plan_name") != plan_name:
        return

    if not user:
        st.session_state.pop("pending_razorpay_checkout", None)
        return

    amount = float(pending["options"]["amount"]) / 100
    billing_label = "/ year" if pending["is_yearly"] else "/ month"
    coupon_code = st.session_state.get("active_coupon_code")

    with st.container(border=True):
        _h(
            f"""
            <div style="padding: 4px 2px 2px;">
                <div style="display: inline-block; color: #A5B4FC; background: rgba(124, 58, 237, 0.16); border: 1px solid rgba(124, 58, 237, 0.45); border-radius: 999px; padding: 3px 9px; font-size: 10px; font-weight: 800; letter-spacing: 0.08em;">✓ SELECTED PLAN</div>
                <div style="font-size: 18px; font-weight: 800; color: #FFFFFF; margin-top: 10px;">💳 Complete Your Payment</div>
                <div style="font-size: 14px; color: #CBD5E1; margin-top: 4px;"><strong>{pending['plan_name'].title()} Plan</strong> · {format_usd(amount)} {billing_label}</div>
                <div style="font-size: 12px; color: #94A3B8; margin-top: 7px;">Secure payment powered by Razorpay</div>
            </div>
            """
        )
        if coupon_code and pending["discount_amount"]:
            st.caption(f"Coupon {coupon_code} is applied. The checkout total reflects your discount.")

        result = _RAZORPAY_CHECKOUT_COMPONENT(
            data={
                "checkout_script": RAZORPAY_CHECKOUT_SCRIPT,
                "checkout_token": pending["checkout_token"],
                "plan_name": pending["plan_name"],
                "is_yearly": pending["is_yearly"],
                "discount_amount": pending["discount_amount"],
                "options": pending["options"],
            },
            key=f"razorpay_checkout_{pending['order_id']}",
            on_payment_change=lambda: None,
            on_failed_change=lambda: None,
        )
        st.caption(
            "Your subscription activates only after Razorpay processes the payment "
            "and the server verifies its signature."
        )

    failure = getattr(result, "failed", None)
    if failure and failure.get("checkout_token") == pending["checkout_token"]:
        failure_key = f"{pending['checkout_token']}:{failure.get('reason', '')}"
        if st.session_state.get("shown_razorpay_checkout_failure") != failure_key:
            st.session_state["shown_razorpay_checkout_failure"] = failure_key
            st.error(f"Payment was not completed. Your subscription remains inactive. {failure.get('reason', '')}")

    payment = getattr(result, "payment", None)
    if not payment:
        return

    # The only browser values accepted are Razorpay's signed response. Plan,
    # billing cycle, and discount must exactly match the server-side context.
    if (
        payment.get("checkout_token") != pending["checkout_token"]
        or payment.get("razorpay_order_id") != pending["order_id"]
        or payment.get("plan") != pending["plan_name"]
        or bool(payment.get("is_yearly")) != pending["is_yearly"]
    ):
        st.error("Payment response did not match this checkout. The plan was NOT activated.")
        return

    callback_key = (
        f"{payment.get('razorpay_order_id')}:{payment.get('razorpay_payment_id')}:"
        f"{payment.get('razorpay_signature')}"
    )
    if st.session_state.get("processed_razorpay_callback") == callback_key:
        return
    st.session_state["processed_razorpay_callback"] = callback_key

    if _activate_verified_payment(
        razorpay_svc=razorpay_svc,
        database=database,
        user=user,
        plan_name=pending["plan_name"],
        is_yearly=pending["is_yearly"],
        discount_amount=pending["discount_amount"],
        order_id=payment.get("razorpay_order_id", ""),
        payment_id=payment.get("razorpay_payment_id", ""),
        signature=payment.get("razorpay_signature", ""),
    ):
        st.session_state.pop("pending_razorpay_checkout", None)
        st.rerun()
