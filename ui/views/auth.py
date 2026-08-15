import datetime
import hashlib
import random
import secrets
import streamlit as st
from uuid import uuid4
from database.database import Database
from models.user import User

__all__ = [
    "get_current_user",
    "render_auth_form",
    "render_top_right_auth_widget",
    "render_auth_view",
    "hash_password",
    "generate_otp",
]

def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())

def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)

def hash_password(password: str) -> str:
    """Hash password using SHA-256 for secure storage."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def generate_otp() -> str:
    """Generate secure 6-digit numeric OTP."""
    return str(secrets.randbelow(900000) + 100000)

def get_current_user(database: Database) -> User | None:
    """Retrieve active authenticated user from session state, or None if unauthenticated/guest."""
    if st.session_state.get("is_logged_in") and st.session_state.get("authenticated_user"):
        return st.session_state["authenticated_user"]
    return None

def render_auth_form(database: Database, key_prefix: str = "auth"):
    """Render interactive login, signup, and OTP forms."""
    pending_email = st.session_state.get("pending_otp_email")

    if pending_email:
        st.markdown("### 📧 Verify Email OTP")
        st.info(f"A 6-digit verification code has been generated for **{pending_email}**.")

        active_otp = database.get_otp(pending_email)
        if not active_otp:
            # Fallback generate fresh OTP if none found
            active_otp = generate_otp()
            expires = (datetime.datetime.now() + datetime.timedelta(minutes=15)).isoformat()
            database.save_otp(pending_email, active_otp, expires)

        _h(
            f"""
            <div style="background: linear-gradient(135deg, rgba(109, 93, 252, 0.25), rgba(0, 212, 255, 0.2)); border: 1.5px solid rgba(109, 93, 252, 0.6); border-radius: 14px; padding: 16px; text-align: center; margin-bottom: 16px;">
                <div style="font-size: 11px; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;">
                    🔒 DEMO CHALLENGE VERIFICATION CODE
                </div>
                <div style="font-size: 32px; font-weight: 800; color: #00D4FF; letter-spacing: 0.25em; margin: 6px 0;">
                    {active_otp}
                </div>
                <div style="font-size: 12px; color: var(--muted);">
                    Dispatched to {pending_email} (Valid for 15 mins)
                </div>
            </div>
            """
        )

        if st.button("⚡ 1-Click Auto-Fill & Verify OTP", type="primary", key=f"{key_prefix}_autofill_otp_btn"):
            database.verify_user(pending_email)
            database.delete_otp(pending_email)
            user = database.get_user_by_email(pending_email)
            if user:
                st.session_state["is_logged_in"] = True
                st.session_state["authenticated_user"] = user
                st.session_state["pending_otp_email"] = None
                st.success(f"✓ Welcome {user.name}! Email verified successfully.")
                st.rerun()

        st.markdown("<div style='text-align: center; color: var(--muted); font-size: 12px; margin: 8px 0;'>— OR ENTER MANUALLY —</div>", unsafe_allow_html=True)

        with st.form(f"{key_prefix}_otp_verification_form"):
            user_otp = st.text_input("Enter 6-Digit OTP", max_chars=6, placeholder=active_otp, key=f"{key_prefix}_otp_input")
            
            c_v, c_r = st.columns([1.5, 1])
            with c_v:
                submit_verify = st.form_submit_button("Verify & Sign In ➔", type="secondary")
            with c_r:
                cancel_verify = st.form_submit_button("Cancel / Back")

            if submit_verify:
                if user_otp.strip() == active_otp:
                    database.verify_user(pending_email)
                    database.delete_otp(pending_email)
                    
                    user = database.get_user_by_email(pending_email)
                    if user:
                        st.session_state["is_logged_in"] = True
                        st.session_state["authenticated_user"] = user
                        st.session_state["pending_otp_email"] = None
                        st.success(f"✓ Welcome {user.name}! Email verified successfully.")
                        st.rerun()
                else:
                    st.error("❌ Invalid OTP code. Please enter the 6-digit code shown above.")

            if cancel_verify:
                st.session_state["pending_otp_email"] = None
                st.rerun()

    else:
        tab_login, tab_signup = st.tabs(["🔑 Sign In", "📝 Create Account"])

        with tab_login:
            with st.form(f"{key_prefix}_login_form"):
                l_email = st.text_input("Email Address", value="demo@agentstock.ai", key=f"{key_prefix}_login_email")
                l_pass = st.text_input("Password", type="password", value="agentstock2026", key=f"{key_prefix}_login_pass")
                
                if st.form_submit_button("Sign In to Workspace ➔", type="primary"):
                    clean_email = l_email.strip().lower()
                    user = database.get_user_by_email(clean_email)
                    if user and user.password_hash == hash_password(l_pass.strip()):
                        st.session_state["is_logged_in"] = True
                        st.session_state["authenticated_user"] = user
                        st.success(f"✓ Welcome back, {user.name}!")
                        st.rerun()
                    else:
                        if clean_email == "demo@agentstock.ai" and l_pass.strip() == "agentstock2026":
                            new_demo_user = User(
                                id=uuid4().hex,
                                name="Vardaan (Founder)",
                                email="demo@agentstock.ai",
                                password_hash=hash_password("agentstock2026"),
                                is_verified=True,
                                created_at=datetime.datetime.now().isoformat(),
                            )
                            database.create_user(new_demo_user)
                            st.session_state["is_logged_in"] = True
                            st.session_state["authenticated_user"] = new_demo_user
                            st.rerun()
                        else:
                            st.error("Invalid email or password. Please check your credentials or create an account.")

            st.divider()
            st.markdown("#### ⚡ Quick Demo Login")
            if st.button("🚀 Sign In as Founder (Vardaan)", key=f"{key_prefix}_quick_demo_btn"):
                demo_user = database.get_user_by_email("demo@agentstock.ai")
                if not demo_user:
                    demo_user = User(
                        id=uuid4().hex,
                        name="Vardaan (Founder)",
                        email="demo@agentstock.ai",
                        password_hash=hash_password("agentstock2026"),
                        is_verified=True,
                        created_at=datetime.datetime.now().isoformat(),
                    )
                    database.create_user(demo_user)
                st.session_state["is_logged_in"] = True
                st.session_state["authenticated_user"] = demo_user
                st.rerun()

        with tab_signup:
            with st.form(f"{key_prefix}_signup_form"):
                s_name = st.text_input("Full Name", value="Alex Mercer", key=f"{key_prefix}_signup_name")
                s_email = st.text_input("Email Address", value="alex@retailer.com", key=f"{key_prefix}_signup_email")
                s_pass = st.text_input("Set Password", type="password", value="SecurePass123!", key=f"{key_prefix}_signup_pass")

                c_s1, c_s2 = st.columns(2)
                with c_s1:
                    submit_instant = st.form_submit_button("🚀 Instant Sign In", type="primary")
                with c_s2:
                    submit_otp = st.form_submit_button("📧 Verify via OTP")

                if submit_instant or submit_otp:
                    clean_name = s_name.strip()
                    clean_email = s_email.strip().lower()
                    clean_pass = s_pass.strip()

                    if not clean_name or not clean_email or not clean_pass:
                        st.error("Please fill in all registration fields.")
                    else:
                        existing = database.get_user_by_email(clean_email)
                        
                        if submit_instant:
                            if not existing:
                                new_user = User(
                                    id=uuid4().hex,
                                    name=clean_name,
                                    email=clean_email,
                                    password_hash=hash_password(clean_pass),
                                    is_verified=True,
                                    created_at=datetime.datetime.now().isoformat(),
                                )
                                database.create_user(new_user)
                                user_to_login = new_user
                            else:
                                database.verify_user(clean_email)
                                user_to_login = existing

                            st.session_state["is_logged_in"] = True
                            st.session_state["authenticated_user"] = user_to_login
                            st.session_state["pending_otp_email"] = None
                            st.success(f"✓ Welcome {user_to_login.name}! Account ready.")
                            st.rerun()

                        elif submit_otp:
                            if not existing:
                                new_user = User(
                                    id=uuid4().hex,
                                    name=clean_name,
                                    email=clean_email,
                                    password_hash=hash_password(clean_pass),
                                    is_verified=False,
                                    created_at=datetime.datetime.now().isoformat(),
                                )
                                database.create_user(new_user)
                            
                            otp_val = generate_otp()
                            expires = (datetime.datetime.now() + datetime.timedelta(minutes=15)).isoformat()
                            database.save_otp(clean_email, otp_val, expires)
                            
                            st.session_state["pending_otp_email"] = clean_email
                            st.success("✓ OTP verification generated! Please verify below.")
                            st.rerun()

def render_top_right_auth_widget(database: Database, key_prefix: str = "hdr"):
    """Render top-right authentication profile or sign-in popover widget."""
    user = get_current_user(database)

    if user:
        from core.billing.subscription_service import SubscriptionService
        plan_name = SubscriptionService(database).get_user_plan(user.id)
        plan_color = "#6D5DFC" if plan_name == "PROFESSIONAL" else ("#F59E0B" if plan_name == "ENTERPRISE" else "#22C55E")

        _h(
            f"""
            <div style="background: rgba(109, 93, 252, 0.12); border: 1px solid rgba(109, 93, 252, 0.35); border-radius: 14px; padding: 12px 16px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: 0.08em;">
                        SIGNED IN USER
                    </div>
                    <div style="font-size: 10px; font-weight: 800; color: {plan_color}; background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);">
                        ⚡ {plan_name}
                    </div>
                </div>
                <div style="font-size: 15px; font-weight: 800; color: #FFFFFF; margin-top: 2px;">
                    👤 {user.name}
                </div>
                <div style="font-size: 11px; color: #4ADE80; font-weight: 600; margin-top: 2px;">
                    ✓ Verified ({user.email})
                </div>
            </div>
            """
        )
        if st.button("🚪 Sign Out", key=f"{key_prefix}_signout_btn"):
            st.session_state["is_logged_in"] = False
            st.session_state["authenticated_user"] = None
            st.session_state["pending_otp_email"] = None
            st.rerun()
    else:
        _h(
            """
            <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 14px; padding: 10px 14px; margin-bottom: 8px;">
                <div style="font-size: 11px; font-weight: 700; color: #F59E0B; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 2px;">
                    👤 GUEST EXPLORER
                </div>
                <div style="font-size: 12px; color: var(--muted);">
                    Sign in to save custom audit logs.
                </div>
            </div>
            """
        )
        with st.popover("🔑 Sign In / Register", icon="🔑", key=f"{key_prefix}_popover"):
            render_auth_form(database, key_prefix=f"{key_prefix}_pop")

def render_auth_view(database: Database) -> User | None:
    """Render full auth view portal if needed."""
    user = get_current_user(database)
    if user:
        return user

    _h(
        """
        <div style="max-width: 520px; margin: 40px auto 20px auto; text-align: center;">
            <div style="font-size: 42px; margin-bottom: 8px;">📦</div>
            <h1 style="font-size: 32px; font-weight: 800; letter-spacing: -0.03em; color: #FFFFFF; margin: 0;">
                AGENTSTOCK AI
            </h1>
            <div style="font-size: 14px; color: var(--accent); font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px;">
                Autonomous Supply Chain & Inventory Decision System
            </div>
        </div>
        """
    )

    col1, col2, col3 = st.columns([1, 2.2, 1])
    with col2:
        render_auth_form(database, key_prefix="full_view")

    return get_current_user(database)

