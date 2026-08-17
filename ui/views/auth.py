"""Enterprise Authentication, Registration, Google OAuth, Legal Consent & OTP Verification View."""
import os
import json
import datetime
import secrets
import time
import streamlit as st
from uuid import uuid4
from database.database import Database
from models.user import User, UserRole
from models.security import UserPolicyConsent
from models.persistence import AdminAuditEvent
from core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    generate_secure_otp,
    hash_otp,
    verify_otp,
    RateLimiter,
    require_policy_consent,
)
from core.config import (
    get_admin_email,
    get_admin_password_hash,
    get_google_client_id,
    get_google_client_secret,
    get_google_redirect_uri,
    get_app_env,
    is_demo_mode,
)

__all__ = [
    "get_current_user",
    "render_auth_form",
    "render_top_right_auth_widget",
    "render_auth_view",
    "hash_password",
    "generate_otp",
]

_USER_SCOPED_SESSION_KEYS = {
    "target_dispatch_supplier_id", "pending_suppliers_tab", "po_sel_sup", "po_sel_prod",
    "selected_voice_product_id", "latest_vision_result", "latest_doc_result",
    "latest_doc_filename", "opened_review", "opened_what_if", "decision_workflow_result",
    "what_if_comparison", "what_if_scenario", "saved_decision_snapshot_id",
    "pending_razorpay_checkout", "processed_razorpay_callback", "active_coupon_code",
    "active_coupon_discount", "active_coupon_discount_type",
}


def clear_user_scoped_session_state() -> None:
    """Remove transient data that must never survive a user switch or logout."""
    for key in _USER_SCOPED_SESSION_KEYS:
        st.session_state.pop(key, None)


def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())


def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


def generate_otp() -> str:
    """Generate secure 6-digit numeric OTP."""
    return generate_secure_otp()


def get_current_user(database: Database) -> User | None:
    """Retrieve active authenticated user from session state."""
    if st.session_state.get("is_logged_in") and st.session_state.get("authenticated_user"):
        return st.session_state["authenticated_user"]
    return None


def _set_authenticated_session(user: User, provider: str) -> None:
    """Set the existing server-side AgentStock session after verified authentication."""
    previous_user = st.session_state.get("authenticated_user")
    if previous_user and getattr(previous_user, "id", None) != user.id:
        clear_user_scoped_session_state()
    st.session_state["is_logged_in"] = True
    st.session_state["authenticated_user"] = user
    st.session_state["is_admin"] = user.role == UserRole.ADMIN.value
    st.session_state["auth_provider"] = provider


def _google_claim(name: str, default=None):
    try:
        return st.user.get(name, default)
    except Exception:
        return default


def synchronize_google_oidc_user(database: Database) -> User | None:
    """Map Streamlit-verified Google OIDC identity into the existing user session."""
    try:
        if not st.user.is_logged_in:
            return None
    except Exception:
        return None

    email = str(_google_claim("email", "")).strip().lower()
    audience = _google_claim("aud")
    issuer = str(_google_claim("iss", ""))
    expires_at = _google_claim("exp")
    expected_client_id = get_google_client_id()
    audience_valid = audience == expected_client_id or (
        isinstance(audience, (list, tuple)) and expected_client_id in audience
    )
    try:
        token_is_current = bool(expires_at) and int(expires_at) > int(time.time())
    except (TypeError, ValueError):
        token_is_current = False
    if (
        not email
        or not bool(_google_claim("email_verified", False))
        or issuer not in {"https://accounts.google.com", "accounts.google.com"}
        or not audience_valid
        or not token_is_current
    ):
        st.session_state["google_oauth_error"] = "Google sign-in could not verify your identity. Please try again."
        try:
            st.logout()
        except Exception:
            pass
        return None

    user = database.get_user_by_email(email)
    if not user:
        user = User(
            id=f"usr_{uuid4().hex[:12]}",
            name=str(_google_claim("name", email.split("@")[0])).strip() or email.split("@")[0],
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role=UserRole.USER.value,
            is_verified=True,
            profile_image_path=str(_google_claim("picture", "")) or None,
        )
        database.create_user(user)

    # Never derive privileges from a Google claim.  An existing account keeps its
    # persisted role (including ADMIN); all newly provisioned Google accounts are
    # created above with the standard USER role.
    if user.is_locked:
        st.session_state["google_oauth_error"] = "This account is locked. Please contact support."
        return None
    if not database.has_accepted_current_policies(email):
        st.session_state["pending_policy_consent_email"] = email
        st.session_state["pending_policy_consent_user_id"] = user.id
        st.session_state["pending_policy_consent_auth_method"] = "google"
        return None

    _set_authenticated_session(user, "google")
    return user


def render_auth_form(database: Database, key_prefix: str = "auth"):
    """Render the active Google-only sign-in flow and mandatory policy consent.

    The email/password/OTP render helpers remain below for a future restoration,
    but are deliberately not reachable from the normal authentication UI.
    """
    pending_consent_email = st.session_state.get("pending_policy_consent_email")

    if pending_consent_email:
        _render_policy_agreement_step(database, pending_consent_email, key_prefix)
    else:
        _render_google_only_sign_in(key_prefix)


def _render_google_only_sign_in(key_prefix: str) -> None:
    """Render the temporary Google OAuth-only entry point."""
    st.caption("Sign in or create your AgentStock account with your Google account.")
    _render_google_oauth_button(f"{key_prefix}_google")


def _render_passwordless_otp_tab(database: Database, key_prefix: str):
    """Render Option A: Passwordless Email OTP authentication."""
    with st.form(f"{key_prefix}_otp_login_form"):
        st.caption("Use your personal or business email (Gmail, Outlook, Yahoo, etc.). No company domain required.")
        o_email = st.text_input("Your Email Address", placeholder="name@gmail.com, outlook, work, etc.", key=f"{key_prefix}_otp_email_input")

        submit_otp_req = st.form_submit_button("Send One-Time Code ➔", type="primary")

        if submit_otp_req:
            clean_email = o_email.strip().lower()
            if not clean_email or "@" not in clean_email:
                st.error("Please enter a valid email address.")
                return

            if RateLimiter.is_rate_limited(f"otp_req_{clean_email}", max_requests=5, window_seconds=60):
                st.error("Too many authentication requests. Please wait 60 seconds before trying again.")
                return

            # Check if user already exists; if not, create initial profile automatically
            user = database.get_user_by_email(clean_email)
            if not user:
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                user = User(
                    id=f"usr_{uuid4().hex[:12]}",
                    name=clean_email.split("@")[0].replace(".", " ").title(),
                    email=clean_email,
                    password_hash=hash_password(secrets.token_urlsafe(32)),
                    role=UserRole.USER.value,
                    is_verified=False,
                    terms_accepted_at=now_iso,
                    privacy_accepted_at=now_iso,
                    aup_accepted_at=now_iso,
                )
                database.create_user(user)

            # Check mandatory policy consent
            if not database.has_accepted_current_policies(clean_email):
                st.session_state["pending_policy_consent_email"] = clean_email
                st.session_state["pending_policy_consent_user_id"] = user.id
                st.rerun()

            # Generate and dispatch 6-digit OTP
            otp_val = generate_secure_otp()
            otp_h = hash_otp(otp_val)
            expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)).isoformat()
            database.save_otp(clean_email, otp_h, expires)

            st.session_state["pending_otp_email"] = clean_email
            if get_app_env() != "production":
                st.session_state["temp_dev_otp_display"] = otp_val
            st.success("✓ 6-digit verification code dispatched to your email address!")
            st.rerun()

    st.markdown("<div style='text-align: center; color: var(--muted); font-size: 12px; margin: 12px 0;'>— OR CONVENIENCE SIGN-IN —</div>", unsafe_allow_html=True)
    _render_google_oauth_button(f"{key_prefix}_otp")


def _render_password_login_tab(database: Database, key_prefix: str):
    """Render Option B: Email + AgentStock Password login."""
    with st.form(f"{key_prefix}_password_login_form"):
        st.caption("Enter your registered email and your AgentStock account password (NOT your Gmail password).")
        l_email = st.text_input("Email Address", placeholder="name@gmail.com, outlook, work, etc.", key=f"{key_prefix}_pass_email")
        l_pass = st.text_input("AgentStock Account Password", type="password", placeholder="••••••••", key=f"{key_prefix}_pass_password")

        submit_login = st.form_submit_button("Sign In with Password ➔", type="primary")

        if submit_login:
            clean_email = l_email.strip().lower()
            clean_pass = l_pass.strip()

            if not clean_email or not clean_pass:
                st.error("Please enter both your email address and AgentStock account password.")
                return

            if RateLimiter.is_rate_limited(f"login_{clean_email}", max_requests=5, window_seconds=60):
                st.error("Too many login attempts. Please wait 60 seconds before trying again.")
                return

            # 1. Platform Admin Verification
            admin_email = get_admin_email()
            admin_hash = get_admin_password_hash()

            if clean_email == admin_email:
                if admin_hash and verify_password(clean_pass, admin_hash):
                    admin_user = database.get_user_by_email(admin_email)
                    if not admin_user:
                        admin_user = User(
                            id="usr_admin_system",
                            name="Platform Administrator",
                            email=admin_email,
                            password_hash=admin_hash,
                            role=UserRole.ADMIN.value,
                            is_verified=True,
                            terms_accepted_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            privacy_accepted_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            aup_accepted_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        )
                        database.create_user(admin_user)

                    if not database.has_accepted_current_policies(clean_email):
                        st.session_state["pending_policy_consent_email"] = clean_email
                        st.session_state["pending_policy_consent_user_id"] = admin_user.id
                        st.rerun()

                    otp_val = generate_secure_otp()
                    otp_h = hash_otp(otp_val)
                    expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)).isoformat()
                    database.save_otp(clean_email, otp_h, expires)
                    st.session_state["pending_otp_email"] = clean_email
                    if get_app_env() != "production":
                        st.session_state["temp_dev_otp_display"] = otp_val
                    st.info("🔐 Admin credentials verified. Enter the 6-digit security OTP for 2FA.")
                    st.rerun()

            # 2. Standard User Password Verification
            user = database.get_user_by_email(clean_email)
            if user and verify_password(clean_pass, user.password_hash):
                if not database.has_accepted_current_policies(clean_email):
                    st.session_state["pending_policy_consent_email"] = clean_email
                    st.session_state["pending_policy_consent_user_id"] = user.id
                    st.rerun()

                otp_val = generate_secure_otp()
                otp_h = hash_otp(otp_val)
                expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)).isoformat()
                database.save_otp(clean_email, otp_h, expires)

                st.session_state["pending_otp_email"] = clean_email
                if get_app_env() != "production":
                    st.session_state["temp_dev_otp_display"] = otp_val
                st.success("✓ Credentials verified! Enter the 6-digit OTP code to complete sign-in.")
                st.rerun()
            else:
                st.error("Invalid email address or password. Please check your credentials.")

    st.markdown("<div style='text-align: center; color: var(--muted); font-size: 12px; margin: 12px 0;'>— OR CONVENIENCE SIGN-IN —</div>", unsafe_allow_html=True)
    _render_google_oauth_button(f"{key_prefix}_pass")


def _render_google_oauth_button(key_prefix: str):
    """Start Streamlit's official Google OpenID Connect flow."""
    g_cid = get_google_client_id()
    g_sec = get_google_client_secret()
    redirect_uri = get_google_redirect_uri()

    if st.button("Continue with Google", icon=":material/login:", key=f"{key_prefix}_google_oauth_btn", width="stretch"):
        if not (g_cid and g_sec and redirect_uri):
            _show_google_oauth_configuration_error(
                "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI before starting Google sign-in."
            )
            return
        try:
            st.login("google")
        except Exception:
            _show_google_oauth_configuration_error(
                "Add the matching [auth] and [auth.google] Streamlit OIDC settings, including the configured redirect URI."
            )


def _show_google_oauth_configuration_error(detail: str) -> None:
    """Show safe, actionable OAuth setup guidance without exposing secrets."""
    if get_app_env() == "production":
        st.error("Google sign-in is temporarily unavailable. Please contact support.")
    else:
        st.error(f"Google OAuth configuration error: {detail}")


def _render_policy_agreement_step(database: Database, pending_email: str, key_prefix: str):
    """Render mandatory Terms, Privacy & Policy agreement modal card before authentication completes."""
    _h(
        """
        <div style="background: rgba(109, 93, 252, 0.08); border: 1px solid rgba(109, 93, 252, 0.3); border-radius: 14px; padding: 20px; margin-bottom: 20px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                <div style="font-size: 24px;">⚖️</div>
                <div style="font-size: 20px; font-weight: 800; color: #FFFFFF;">Before you continue</div>
            </div>
            <div style="font-size: 13.5px; color: #CBD5E1; line-height: 1.6;">
                AgentStock AI helps businesses manage inventory, suppliers, stock documents, and inventory-related communications.
                Before signing in, please review and accept the policies that govern your use of the service.
            </div>
        </div>
        """
    )

    with st.expander("📄 Review Applicable Terms & Policies (v1.0)", expanded=False):
        t_tab1, t_tab2, t_tab3, t_tab4, t_tab5, t_tab6 = st.tabs([
            "Terms", "Privacy", "Acceptable Use", "Billing", "Comms", "Security"
        ])
        with t_tab1:
            st.markdown("""
            **Terms of Service (v1.0)**
            - AgentStock AI is an inventory decision-support platform designed for legitimate commercial entities.
            - Recommendations are advisory; business proprietors maintain ultimate decision authority over stock procurement and order dispatch.
            - Account credentials and API tokens must be safeguarded with reasonable security practices.
            """)
        with t_tab2:
            st.markdown("""
            **Privacy Policy (v1.0)**
            - Your business catalog, sales data, supplier lists, and purchase orders are strictly partitioned per-tenant.
            - We adhere to GDPR & DPDP compliance standards; inventory records are never sold or rented to third-party brokers.
            """)
        with t_tab3:
            st.markdown("""
            **Acceptable Use Policy (v1.0)**
            - Platform services may only be utilized for lawful inventory management, supplier relations, and stock forecasting.
            - Prohibited activities include reverse engineering, processing illegal merchandise data, scraping, or spamming suppliers.
            """)
        with t_tab4:
            st.markdown("""
            **Subscription & Billing Policy (v1.0)**
            - Subscriptions are billed in advance on recurring monthly or annual intervals via Razorpay.
            - Cancellation takes effect at the end of the current billing cycle. Transparent prorations apply on plan upgrades.
            """)
        with t_tab5:
            st.markdown("""
            **Communication Policy (v1.0)**
            - WhatsApp, Email, and Phone dispatch actions initiate real-time communication on behalf of the registered business owner.
            - Users are solely responsible for compliance with anti-spam statutes and commercial contact consent.
            """)
        with t_tab6:
            st.markdown("""
            **Data & Security Policy (v1.0)**
            - Passwords and OTP codes are protected with cryptographic PBKDF2/HMAC hashing.
            - Document processing strips ephemeral memory buffers post-OCR extraction.
            """)

    with st.form(f"{key_prefix}_policy_agreement_form"):
        # Mandatory checkbox MUST start unchecked (value=False)
        agreed = st.checkbox(
            "I have read and agree to the AgentStock AI Terms of Service, Privacy Policy, Acceptable Use Policy, Subscription & Billing Policy, Communication Policy, and Data & Security Policy.",
            value=False,
            key=f"{key_prefix}_chk_policy_agree",
        )

        c_sub, c_can = st.columns([1.5, 1])
        with c_sub:
            submit_consent = st.form_submit_button("I Agree & Continue ➔", type="primary")
        with c_can:
            cancel_consent = st.form_submit_button("Cancel / Back")

        if submit_consent:
            if not agreed:
                st.warning("Please confirm that you have read and agree to the applicable policies before continuing.")
                return

            user_id = st.session_state.get("pending_policy_consent_user_id")
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            consent_record = UserPolicyConsent(
                id=f"cons_{uuid4().hex[:14]}",
                user_id=user_id,
                email=pending_email,
                policy_version="1.0",
                terms_version="1.0",
                privacy_version="1.0",
                acceptable_use_version="1.0",
                subscription_policy_version="1.0",
                communication_policy_version="1.0",
                data_security_policy_version="1.0",
                consent_status="ACCEPTED",
                agreed_at=now_iso,
                created_at=now_iso,
            )
            database.record_policy_consent(consent_record)

            audit_event = AdminAuditEvent(
                id=f"evt_{uuid4().hex[:14]}",
                user_id=user_id,
                user_email=pending_email,
                event_type="POLICY_CONSENT_ACCEPTED",
                entity_type="POLICY",
                entity_id=consent_record.id,
                metadata_json=json.dumps({
                    "terms_version": "1.0",
                    "privacy_version": "1.0",
                    "acceptable_use_version": "1.0",
                    "subscription_policy_version": "1.0",
                    "communication_policy_version": "1.0",
                    "data_security_policy_version": "1.0",
                    "consent_id": consent_record.id,
                }),
                security_classification="STANDARD",
            )
            database.create_admin_audit_event(audit_event)

            st.session_state.pop("pending_policy_consent_email", None)
            st.session_state.pop("pending_policy_consent_user_id", None)

            if st.session_state.pop("pending_policy_consent_auth_method", None) == "google":
                database.verify_user(pending_email)
                user = database.get_user_by_email(pending_email)
                if user:
                    _set_authenticated_session(user, "google")
                    st.success(f"✓ Welcome {user.name}! Google identity verified.")
                    st.rerun()
                return

            otp_val = generate_secure_otp()
            otp_h = hash_otp(otp_val)
            expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)).isoformat()
            database.save_otp(pending_email, otp_h, expires)

            st.session_state["pending_otp_email"] = pending_email
            if get_app_env() != "production":
                st.session_state["temp_dev_otp_display"] = otp_val
            st.success("✓ Policy consent recorded! Enter the 6-digit verification code to complete sign-in.")
            st.rerun()

        if cancel_consent:
            st.session_state.pop("pending_policy_consent_email", None)
            st.session_state.pop("pending_policy_consent_user_id", None)
            st.rerun()


def _render_signup_tab(database: Database, key_prefix: str):
    """Render user registration form accepting any normal email address."""
    with st.form(f"{key_prefix}_signup_form"):
        s_name = st.text_input("Full Name / Store Owner", placeholder="Jane Doe", key=f"{key_prefix}_signup_name")
        s_email = st.text_input("Email Address", placeholder="jane@gmail.com, outlook, work, etc.", key=f"{key_prefix}_signup_email")
        s_pass = st.text_input("Create AgentStock Password", type="password", placeholder="Min. 8 chars, 1 uppercase, 1 number", key=f"{key_prefix}_signup_pass")
        st.caption("Create a password for your AgentStock account (NOT your Gmail or email provider password).")

        agree_terms = st.checkbox(
            "I have read and agree to the AgentStock AI Terms of Service, Privacy Policy, Acceptable Use Policy, Subscription & Billing Policy, Communication Policy, and Data & Security Policy.",
            value=False,
            key=f"{key_prefix}_agree_legal",
        )

        submit_signup = st.form_submit_button("Create Account ➔", type="primary")

        if submit_signup:
            clean_name = s_name.strip()
            clean_email = s_email.strip().lower()
            clean_pass = s_pass.strip()

            if not clean_name or not clean_email or not clean_pass:
                st.error("Please fill in all required fields.")
                return

            if not agree_terms:
                st.warning("Please confirm that you have read and agree to the applicable policies before continuing.")
                return

            is_strong, pass_msg = validate_password_strength(clean_pass)
            if not is_strong:
                st.error(pass_msg)
                return

            existing = database.get_user_by_email(clean_email)
            if existing:
                st.error("An account with this email address already exists. Please sign in.")
                return

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            user_id = f"usr_{uuid4().hex[:12]}"
            new_user = User(
                id=user_id,
                name=clean_name,
                email=clean_email,
                password_hash=hash_password(clean_pass),
                role=UserRole.USER.value,
                is_verified=False,
                terms_accepted_at=now_iso,
                privacy_accepted_at=now_iso,
                aup_accepted_at=now_iso,
            )
            database.create_user(new_user)

            consent_record = UserPolicyConsent(
                id=f"cons_{uuid4().hex[:14]}",
                user_id=user_id,
                email=clean_email,
                policy_version="1.0",
                terms_version="1.0",
                privacy_version="1.0",
                acceptable_use_version="1.0",
                subscription_policy_version="1.0",
                communication_policy_version="1.0",
                data_security_policy_version="1.0",
                consent_status="ACCEPTED",
                agreed_at=now_iso,
                created_at=now_iso,
            )
            database.record_policy_consent(consent_record)

            audit_event = AdminAuditEvent(
                id=f"evt_{uuid4().hex[:14]}",
                user_id=user_id,
                user_email=clean_email,
                event_type="POLICY_CONSENT_ACCEPTED",
                entity_type="REGISTRATION",
                entity_id=consent_record.id,
                metadata_json=json.dumps({
                    "terms_version": "1.0",
                    "privacy_version": "1.0",
                    "acceptable_use_version": "1.0",
                    "subscription_policy_version": "1.0",
                    "communication_policy_version": "1.0",
                    "data_security_policy_version": "1.0",
                    "consent_id": consent_record.id,
                }),
                security_classification="STANDARD",
            )
            database.create_admin_audit_event(audit_event)

            otp_val = generate_secure_otp()
            otp_h = hash_otp(otp_val)
            expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)).isoformat()
            database.save_otp(clean_email, otp_h, expires)

            st.session_state["pending_otp_email"] = clean_email
            if get_app_env() != "production":
                st.session_state["temp_dev_otp_display"] = otp_val
            st.success("✓ Account created! A 6-digit verification code has been dispatched.")
            st.rerun()


def _render_otp_step(database: Database, pending_email: str, key_prefix: str):
    """Render secure OTP verification screen."""
    st.markdown("### 📧 Verify Your Email Identity")
    st.info(f"Enter the 6-digit verification code sent to **{pending_email}** (valid for 15 minutes).")

    with st.form(f"{key_prefix}_otp_form"):
        user_otp = st.text_input("Enter 6-Digit Verification Code", max_chars=6, placeholder="••••••", key=f"{key_prefix}_otp_input")

        c_v, c_c = st.columns([1.5, 1])
        with c_v:
            submit_verify = st.form_submit_button("Verify & Sign In ➔", type="primary")
        with c_c:
            cancel_verify = st.form_submit_button("Cancel / Back")

        if submit_verify:
            otp_rec = database.get_otp_record(pending_email)
            if not otp_rec:
                st.error("No active verification code found for this email. Please request a new one.")
                return

            if otp_rec.attempts >= otp_rec.max_attempts:
                st.error("Maximum verification attempts exceeded. Please request a new code.")
                database.delete_otp(pending_email)
                st.session_state["pending_otp_email"] = None
                st.rerun()

            entered_clean = user_otp.strip()
            dev_otp_matches = (
                get_app_env() != "production"
                and entered_clean == st.session_state.get("temp_dev_otp_display")
            )
            if verify_otp(entered_clean, otp_rec.otp_hash) or dev_otp_matches:
                database.verify_user(pending_email)
                database.delete_otp(pending_email)
                user = database.get_user_by_email(pending_email)
                if user:
                    _set_authenticated_session(user, "email_otp")
                    st.session_state["pending_otp_email"] = None
                    st.session_state.pop("temp_dev_otp_display", None)
                    st.success(f"✓ Welcome {user.name}! Session authenticated.")
                    st.rerun()
            else:
                database.increment_otp_attempts(pending_email)
                st.error(f"❌ Invalid verification code. Attempts remaining: {otp_rec.max_attempts - otp_rec.attempts - 1}")

        if cancel_verify:
            st.session_state["pending_otp_email"] = None
            st.rerun()


def render_top_right_auth_widget(database: Database, key_prefix: str = "hdr"):
    """Render top-right authentication status badge or sign-in popover."""
    user = get_current_user(database)

    if user:
        from core.billing.subscription_service import SubscriptionService
        sub_svc = SubscriptionService(database)
        plan_name = sub_svc.get_user_plan(user.id)
        role_tag = "👑 ADMIN" if user.is_admin else f"⚡ {plan_name}"
        tag_color = "#F59E0B" if user.is_admin else ("#6D5DFC" if plan_name == "PROFESSIONAL" else "#22C55E")

        _h(
            f"""
            <div style="background: rgba(109, 93, 252, 0.12); border: 1px solid rgba(109, 93, 252, 0.35); border-radius: 14px; padding: 10px 14px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: 0.08em;">
                        AUTHENTICATED
                    </div>
                    <div style="font-size: 10px; font-weight: 800; color: {tag_color}; background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 10px;">
                        {role_tag}
                    </div>
                </div>
                <div style="font-size: 14px; font-weight: 800; color: #FFFFFF; margin-top: 2px;">
                    👤 {user.name}
                </div>
                <div style="font-size: 11px; color: #4ADE80; margin-top: 1px;">
                    ✓ {user.email}
                </div>
            </div>
            """
        )
        if st.button("🚪 Sign Out", key=f"{key_prefix}_signout_btn", width="stretch"):
            if st.session_state.get("auth_provider") == "google":
                st.logout()
            st.session_state["is_logged_in"] = False
            st.session_state["authenticated_user"] = None
            st.session_state["is_admin"] = False
            clear_user_scoped_session_state()
            st.session_state.pop("auth_provider", None)
            st.session_state["pending_otp_email"] = None
            st.session_state["pending_policy_consent_email"] = None
            st.rerun()
    else:
        _h(
            """
            <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 14px; padding: 10px 14px; margin-bottom: 8px;">
                <div style="font-size: 11px; font-weight: 700; color: #F59E0B; text-transform: uppercase; letter-spacing: 0.08em;">
                    WORKSPACE
                </div>
                <div style="font-size: 13px; color: var(--muted); margin-top: 2px;">
                    Sign in to access your business stock.
                </div>
            </div>
            """
        )
        with st.popover("🔑 Sign In / Register", icon="🔑", key=f"{key_prefix}_popover"):
            render_auth_form(database, key_prefix=f"{key_prefix}_pop")


def render_auth_view(database: Database) -> User | None:
    """Render full standalone authentication portal."""
    user = get_current_user(database)
    if user:
        return user

    _h(
        """
        <div style="max-width: 520px; margin: 40px auto 20px auto; text-align: center;">
            <div style="font-size: 42px; margin-bottom: 8px;">⚡</div>
            <h1 style="font-size: 32px; font-weight: 800; letter-spacing: -0.03em; color: #FFFFFF; margin: 0;">
                AgentStock AI
            </h1>
            <div style="font-size: 14px; color: var(--accent); font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px;">
                AI-Powered Inventory Intelligence
            </div>
        </div>
        """
    )

    col1, col2, col3 = st.columns([1, 2.2, 1])
    with col2:
        render_auth_form(database, key_prefix="full_view")

    return get_current_user(database)
