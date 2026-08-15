"""Stripe Checkout and Customer Portal integration service."""
import os
from typing import Optional, Dict, Any
from core.config import (
    get_stripe_secret_key,
    get_stripe_price_id,
    get_app_base_url,
    get_stripe_webhook_secret,
)

try:
    import stripe
except ImportError:
    stripe = None


class StripeBillingService:
    """Encapsulates Stripe API calls for subscription checkout and customer portal."""

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or get_stripe_secret_key()
        if stripe and self.secret_key:
            stripe.api_key = self.secret_key

    def is_configured(self) -> bool:
        """Check if live or test Stripe API keys are configured."""
        return bool(stripe and self.secret_key and not self.secret_key.startswith("sk_test_placeholder"))

    def create_checkout_session(
        self,
        user_id: str,
        user_email: str,
        plan_name: str,
        is_yearly: bool = False,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe Checkout Session for subscription."""
        base_url = get_app_base_url().rstrip("/")
        s_url = success_url or f"{base_url}/?checkout_status=success&session_id={{CHECKOUT_SESSION_ID}}&plan={plan_name}"
        c_url = cancel_url or f"{base_url}/?checkout_status=cancel&plan={plan_name}"
        price_id = get_stripe_price_id(plan_name, is_yearly)

        if not self.is_configured():
            # Graceful test/sandbox mock session generator
            mock_session_id = f"cs_test_mock_{user_id[:8]}_{plan_name.lower()}"
            return {
                "id": mock_session_id,
                "url": f"{base_url}/?checkout_status=success&session_id={mock_session_id}&plan={plan_name}&mock=true",
                "mode": "mock",
                "price_id": price_id,
            }

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=user_email,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=s_url,
            cancel_url=c_url,
            metadata={
                "user_id": user_id,
                "plan_name": plan_name.upper(),
                "is_yearly": str(is_yearly).lower(),
            },
            subscription_data={
                "metadata": {
                    "user_id": user_id,
                    "plan_name": plan_name.upper(),
                }
            },
        )
        return {
            "id": session.id,
            "url": session.url,
            "mode": "live",
            "price_id": price_id,
        }

    def create_customer_portal_session(
        self,
        stripe_customer_id: str,
        return_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe Customer Portal session for subscription management."""
        base_url = get_app_base_url().rstrip("/")
        r_url = return_url or f"{base_url}/"

        if not self.is_configured():
            return {
                "url": f"{base_url}/?portal=mock_active",
                "mode": "mock",
            }

        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=r_url,
        )
        return {
            "url": session.url,
            "mode": "live",
        }

    def construct_webhook_event(
        self,
        payload: bytes,
        sig_header: str,
        webhook_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify Stripe webhook signature and construct event."""
        secret = webhook_secret or get_stripe_webhook_secret()
        if not secret:
            raise ValueError("Stripe webhook signing secret is not configured.")
        if not stripe:
            raise RuntimeError("Stripe SDK is not installed.")

        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=secret,
        )
        return event
