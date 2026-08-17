"""Razorpay Payment Gateway & Webhook Signature Verification Service."""
import hmac
import hashlib
import secrets
from typing import Optional, Dict, Any

import requests

from core.config import (
    get_razorpay_key_id,
    get_razorpay_key_secret,
    get_razorpay_webhook_secret,
    get_plan_pricing,
)


class RazorpayBillingService:
    """Razorpay order creation, Checkout verification, and webhook signature validation."""

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ):
        self.key_id = key_id or get_razorpay_key_id()
        self.key_secret = key_secret or get_razorpay_key_secret()
        self.webhook_secret = webhook_secret or get_razorpay_webhook_secret()

    def get_checkout_key_id(self) -> Optional[str]:
        """Return the public Razorpay key used by Checkout."""
        return self.key_id

    def _credentials_configured(self) -> bool:
        return bool(self.key_id and self.key_secret)

    def create_order(
        self,
        user_id: str,
        user_email: str,
        plan_name: str,
        is_yearly: bool = False,
        discount_amount: float = 0.0,
        discount_type: str = "PERCENTAGE",
    ) -> Dict[str, Any]:
        """Create a real Razorpay order. Never fabricate a paid/successful order."""
        pricing = get_plan_pricing(plan_name, is_yearly)

        base_rate = pricing["yearly_usd"] * 12 if is_yearly else pricing["monthly_usd"]

        if discount_amount > 0 and discount_type.upper() == "FIXED":
            final_rate = max(0.0, base_rate - discount_amount)
        elif discount_amount > 0:
            final_rate = max(0.0, base_rate * (1 - discount_amount / 100.0))
        else:
            final_rate = float(base_rate)

        amount_in_smallest_unit = int(round(final_rate * 100))
        if amount_in_smallest_unit <= 0:
            raise ValueError("The final subscription amount must be greater than zero.")

        if not self._credentials_configured():
            raise RuntimeError(
                "Razorpay Key ID/Secret are not configured. "
                "Refusing to activate a subscription without a real payment gateway."
            )

        receipt_id = f"rcpt_{user_id[:8]}_{secrets.token_hex(4)}"

        try:
            resp = requests.post(
                "https://api.razorpay.com/v1/orders",
                auth=(self.key_id, self.key_secret),
                json={
                    "amount": amount_in_smallest_unit,
                    "currency": pricing["currency"],
                    "receipt": receipt_id,
                    "notes": {
                        "user_id": user_id,
                        "user_email": user_email,
                        "plan_name": plan_name.upper(),
                        "is_yearly": str(is_yearly),
                    },
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Unable to reach Razorpay: {exc}") from exc

        if resp.status_code not in (200, 201):
            try:
                details = resp.json()
            except ValueError:
                details = resp.text
            raise RuntimeError(
                f"Razorpay order creation failed (HTTP {resp.status_code}): {details}"
            )

        order = resp.json()

        if not order.get("id") or order.get("status") != "created":
            raise RuntimeError(
                f"Razorpay returned an invalid order response: {order}"
            )

        return order

    def verify_payment(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        """
        Verify the Checkout signature and confirm the payment belongs to the order.

        Subscription activation is allowed only after both checks pass.
        """
        if not self.key_secret:
            raise RuntimeError(
                "Razorpay secret is not configured. Payment cannot be verified."
            )

        if not order_id or not payment_id or not signature:
            return False

        if not self.verify_payment_signature(order_id, payment_id, signature):
            return False

        # Ask Razorpay for the payment itself. This prevents trusting browser-only
        # parameters even after the HMAC signature has been checked.
        try:
            resp = requests.get(
                f"https://api.razorpay.com/v1/payments/{payment_id}",
                auth=(self.key_id, self.key_secret),
                timeout=15,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Unable to verify payment with Razorpay: {exc}") from exc

        if resp.status_code != 200:
            return False

        payment = resp.json()

        if payment.get("order_id") != order_id:
            return False

        # Captured is the safest state for granting paid entitlements.
        return payment.get("status") == "captured"

    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> bool:
        """Verify HMAC-SHA256 signature returned by Razorpay Checkout."""
        if not self.key_secret:
            return False

        message = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
        expected_signature = hmac.new(
            self.key_secret.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_signature, razorpay_signature)

    def generate_mock_payment_signature(self, order_id: str, payment_id: str) -> str:
        """Helper retained for unit tests."""
        secret = self.key_secret or "mock_secret"
        msg = f"{order_id}|{payment_id}".encode("utf-8")
        return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    def verify_webhook_signature(
        self,
        webhook_body_bytes: bytes,
        webhook_signature: str,
    ) -> bool:
        """Verify Razorpay webhook HMAC-SHA256 signature."""
        if not self.webhook_secret:
            return False

        expected_signature = hmac.new(
            self.webhook_secret.encode("utf-8"),
            webhook_body_bytes,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_signature, webhook_signature)

    def generate_mock_webhook_signature(self, payload: bytes) -> str:
        """Helper retained for unit tests."""
        secret = self.webhook_secret or "mock_webhook_secret"
        return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
