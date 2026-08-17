"""Centralized configuration service for AgentStock AI.

Safely resolves environment variables and Streamlit secrets without
leaking credentials or using insecure production fallbacks.
"""

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def _get_secret_or_env(
    key: str, default: Optional[str] = None
) -> Optional[str]:
    """Retrieve a value from Streamlit secrets or OS environment."""
    try:
        import streamlit as st

        if hasattr(st, "secrets") and key in st.secrets:
            value = st.secrets[key]

            # Avoid treating an empty secret as a valid secret.
            if value is not None and str(value).strip():
                return str(value).strip()

    except Exception:
        # Streamlit secrets may not be available during CLI/tests.
        pass

    value = os.environ.get(key)

    if value is not None and value.strip():
        return value.strip()

    return default


def get_gemini_api_key() -> Optional[str]:
    """Retrieve Gemini API key safely."""
    return _get_secret_or_env("GEMINI_API_KEY") or _get_secret_or_env(
        "GOOGLE_API_KEY"
    )


def get_app_env() -> str:
    """Retrieve application environment.

    Expected values:
        development
        testing
        production
    """
    return _get_secret_or_env("APP_ENV", "development").lower()


def is_demo_mode() -> bool:
    """Check whether internal demo/test mode is explicitly enabled.

    Production should always set:
        DEMO_MODE=false
    """
    val = _get_secret_or_env("DEMO_MODE", "false").lower()
    return val in {"true", "1", "yes"}


def get_secret_key() -> str:
    """Retrieve the application encryption/session signing secret.

    Production security:
    - SECRET_KEY MUST be explicitly configured.
    - There is intentionally no hard-coded production secret.

    Local development:
    - A development-only fallback is allowed so the application can run
      without requiring production credentials.
    """
    secret = _get_secret_or_env("SECRET_KEY")

    if secret:
        return secret

    if get_app_env() == "production":
        raise RuntimeError(
            "SECRET_KEY is required in production. "
            "Configure it through Streamlit Secrets or the environment."
        )

    return "local-development-only-secret"


def get_database_url() -> str:
    """Retrieve database URL.

    Local development defaults to SQLite.
    Production should provide DATABASE_URL, preferably PostgreSQL.
    """
    return _get_secret_or_env(
        "DATABASE_URL",
        "sqlite:///agentstock.db",
    )


# ---------------------------------------------------------------------------
# Razorpay Configuration
# ---------------------------------------------------------------------------

def get_razorpay_key_id() -> Optional[str]:
    """Retrieve Razorpay public key ID."""
    return _get_secret_or_env("RAZORPAY_KEY_ID")


def get_razorpay_key_secret() -> Optional[str]:
    """Retrieve Razorpay private key secret."""
    return _get_secret_or_env("RAZORPAY_KEY_SECRET")


def get_razorpay_webhook_secret() -> Optional[str]:
    """Retrieve Razorpay webhook signing secret."""
    return _get_secret_or_env("RAZORPAY_WEBHOOK_SECRET")


# ---------------------------------------------------------------------------
# Admin Configuration
# ---------------------------------------------------------------------------

def get_admin_email() -> str:
    """Retrieve the configured administrator email."""
    return (_get_secret_or_env("ADMIN_EMAIL") or "").strip().lower()


def get_admin_password_hash() -> Optional[str]:
    """Retrieve the administrator password hash."""
    return _get_secret_or_env("ADMIN_PASSWORD_HASH")


# ---------------------------------------------------------------------------
# Google OAuth / OIDC Configuration
# ---------------------------------------------------------------------------

def _get_google_oidc_secret(key: str) -> Optional[str]:
    """Read Google OIDC configuration from Streamlit secrets."""
    try:
        import streamlit as st

        auth_config = st.secrets.get("auth", {})
        google_config = auth_config.get("google", {})

        value = google_config.get(key)

        if value:
            return str(value).strip()

    except Exception:
        return None

    return None


def get_google_client_id() -> Optional[str]:
    """Retrieve Google OAuth client ID."""
    return _get_secret_or_env(
        "GOOGLE_CLIENT_ID"
    ) or _get_google_oidc_secret("client_id")


def get_google_client_secret() -> Optional[str]:
    """Retrieve Google OAuth client secret."""
    return _get_secret_or_env(
        "GOOGLE_CLIENT_SECRET"
    ) or _get_google_oidc_secret("client_secret")


def get_google_redirect_uri() -> Optional[str]:
    """Retrieve Google OAuth redirect URI."""
    redirect_uri = _get_secret_or_env("GOOGLE_REDIRECT_URI")

    if redirect_uri:
        return redirect_uri

    try:
        import streamlit as st

        value = st.secrets.get("auth", {}).get("redirect_uri")

        if value:
            return str(value).strip()

    except Exception:
        return None

    return None


# ---------------------------------------------------------------------------
# SMTP / Email Configuration
# ---------------------------------------------------------------------------

def get_smtp_config() -> dict:
    """Retrieve SMTP email configuration."""
    return {
        "host": _get_secret_or_env("SMTP_HOST", ""),
        "port": int(_get_secret_or_env("SMTP_PORT", "587")),
        "username": _get_secret_or_env("SMTP_USERNAME", ""),
        "password": _get_secret_or_env("SMTP_PASSWORD", ""),
        "from_email": _get_secret_or_env(
            "SMTP_FROM_EMAIL",
            "notifications@agentstock.ai",
        ),
    }


# ---------------------------------------------------------------------------
# Application URL Configuration
# ---------------------------------------------------------------------------

def get_app_base_url() -> str:
    """Retrieve the application base URL.

    Local development:
        http://localhost:8501

    Production:
        Must be explicitly configured through APP_BASE_URL.
    """
    base_url = _get_secret_or_env("APP_BASE_URL")

    if base_url:
        return base_url.rstrip("/")

    if get_app_env() == "production":
        raise RuntimeError(
            "APP_BASE_URL is required in production. "
            "Configure it through Streamlit Secrets or the environment."
        )

    return "http://localhost:8501"


# ---------------------------------------------------------------------------
# Subscription Plans
# ---------------------------------------------------------------------------

PLAN_PRICING = {
    "STARTER": {
        "name": "Starter",
        "currency": "USD",
        "monthly_usd": 19.0,
        "yearly_usd": 15.0,
        "camera_scans": 100,
        "voice_queries": 250,
        "ai_decisions": 500,
        "documents_analyzed": 50,
        "max_suppliers": 20,
        "max_products": 250,
    },
    "PROFESSIONAL": {
        "name": "Professional",
        "currency": "USD",
        "monthly_usd": 49.0,
        "yearly_usd": 39.0,
        "camera_scans": 1000,
        "voice_queries": 1500,
        "ai_decisions": 99999,
        "documents_analyzed": 500,
        "max_suppliers": 100,
        "max_products": 2500,
    },
    "ENTERPRISE": {
        "name": "Enterprise",
        "currency": "USD",
        "monthly_usd": 149.0,
        "yearly_usd": 119.0,
        "camera_scans": 99999,
        "voice_queries": 99999,
        "ai_decisions": 99999,
        "documents_analyzed": 99999,
        "max_suppliers": 99999,
        "max_products": 99999,
    },
}


def get_plan_pricing(plan_name: str, is_yearly: bool = False) -> dict:
    """Return a copy of the authoritative plan configuration.

    The is_yearly parameter is retained for compatibility with existing
    callers. The returned dictionary contains both monthly and yearly
    pricing fields.
    """
    return dict(
        PLAN_PRICING.get(
            plan_name.upper(),
            PLAN_PRICING["STARTER"],
        )
    )


def format_usd(amount: float) -> str:
    """Format a USD amount without unnecessary decimal places."""
    amount = float(amount)

    return (
        f"${amount:,.0f}"
        if amount.is_integer()
        else f"${amount:,.2f}"
    )