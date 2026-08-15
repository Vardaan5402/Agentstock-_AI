"""Centralized configuration service for AgentStock AI.

Safely resolves environment variables and Streamlit secrets without leaking credentials.
"""
import os
from typing import Optional


def _get_secret_or_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve secret from Streamlit secrets or OS environment."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)


def get_gemini_api_key() -> Optional[str]:
    """Retrieve Gemini API Key safely."""
    return _get_secret_or_env("GEMINI_API_KEY") or _get_secret_or_env("GOOGLE_API_KEY")


def get_stripe_secret_key() -> Optional[str]:
    """Retrieve Stripe Secret Key."""
    return _get_secret_or_env("STRIPE_SECRET_KEY")


def get_stripe_publishable_key() -> Optional[str]:
    """Retrieve Stripe Publishable Key."""
    return _get_secret_or_env("STRIPE_PUBLISHABLE_KEY")


def get_stripe_webhook_secret() -> Optional[str]:
    """Retrieve Stripe Webhook Signing Secret."""
    return _get_secret_or_env("STRIPE_WEBHOOK_SECRET")


def get_app_base_url() -> str:
    """Retrieve base application URL for Stripe Checkout redirects."""
    return _get_secret_or_env("APP_BASE_URL", "http://localhost:8501")


def get_stripe_price_id(plan_name: str, is_yearly: bool = False) -> str:
    """Resolve Stripe Price ID for an existing AgentStock AI plan."""
    plan_upper = plan_name.upper()
    cycle = "YEARLY" if is_yearly else "MONTHLY"
    key = f"STRIPE_PRICE_{plan_upper}_{cycle}"
    
    # Check configured secrets/env or provide standard test mode fallback identifiers
    val = _get_secret_or_env(key)
    if val:
        return val
        
    fallback_map = {
        ("STARTER", False): "price_starter_monthly_usd_19",
        ("STARTER", True): "price_starter_yearly_usd_15",
        ("PROFESSIONAL", False): "price_pro_monthly_usd_49",
        ("PROFESSIONAL", True): "price_pro_yearly_usd_39",
        ("ENTERPRISE", False): "price_enterprise_monthly_usd_149",
        ("ENTERPRISE", True): "price_enterprise_yearly_usd_119",
    }
    return fallback_map.get((plan_upper, is_yearly), f"price_{plan_upper.lower()}_{cycle.lower()}")
