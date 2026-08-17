"""Interactive 12-Step Guided Onboarding Tour for Business Owners."""
import streamlit as st
from database.database import Database
from core.onboarding import OnboardingTourService
from ui.views.auth import get_current_user


def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())


def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


def render_onboarding_view(database: Database):
    """Render 12-step interactive guided tour."""
    user = get_current_user(database)
    current_step = st.session_state.get("onboarding_current_step", 1)
    total_steps = OnboardingTourService.total_steps()

    step_data = OnboardingTourService.get_step(current_step)

    _h(
        f"""
        <div style="max-width: 720px; margin: 20px auto; text-align: center;">
            <div style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 0.12em; text-transform: uppercase;">
                🚀 STEP {current_step} OF {total_steps} • GETTING STARTED
            </div>
            <h1 style="font-size: 34px; font-weight: 800; letter-spacing: -0.02em; margin: 8px 0; color: #FFFFFF;">
                {step_data['title']}
            </h1>
        </div>
        """
    )

    # Progress bar
    progress_val = float(current_step) / float(total_steps)
    st.progress(progress_val)

    # Step Card
    _h(
        f"""
        <div class="agent-card" style="max-width: 720px; margin: 20px auto; padding: 32px; text-align: center; border-top: 3px solid #6D5DFC;">
            <div style="font-size: 54px; margin-bottom: 16px;">{step_data['icon']}</div>
            <p style="font-size: 17px; color: #CBD5E1; line-height: 1.7; max-width: 600px; margin: 0 auto 24px auto;">
                {step_data['description']}
            </p>
        </div>
        """
    )

    # Navigation buttons
    col_b1, col_b2, col_b3 = st.columns([1, 2, 1])

    with col_b1:
        if current_step > 1:
            if st.button("⬅️ Previous", key="btn_ob_prev", width="stretch"):
                st.session_state["onboarding_current_step"] = current_step - 1
                st.rerun()

    with col_b3:
        if current_step < total_steps:
            if st.button(step_data["action_text"], type="primary", key="btn_ob_next", width="stretch"):
                st.session_state["onboarding_current_step"] = current_step + 1
                st.rerun()
        else:
            if st.button("🎉 Finish & Go to Dashboard", type="primary", key="btn_ob_finish", width="stretch"):
                if user:
                    user.onboarding_completed = True
                    database.update_user(user)
                st.session_state["selected_nav_page"] = "📊 Workspace Dashboard"
                st.rerun()

    with col_b2:
        if st.button("Skip Tour & Go to Workspace", key="btn_ob_skip"):
            if user:
                user.onboarding_completed = True
                database.update_user(user)
            st.session_state["selected_nav_page"] = "📊 Workspace Dashboard"
            st.rerun()
