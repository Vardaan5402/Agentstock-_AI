"""Verified, idempotent Razorpay webhook processing."""
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from typing import Any

from database.database import Database
from models.subscription import UserSubscription, SubscriptionStatus, BillingCycle, PlanTier


class RazorpayWebhookProcessor:
    """Persist lifecycle changes only from a verified Razorpay delivery."""

    ACTIVE_EVENTS = {"payment.captured", "order.paid", "subscription.activated", "subscription.charged"}
    INACTIVE_EVENTS = {
        "payment.failed": SubscriptionStatus.PAST_DUE.value,
        "subscription.pending": SubscriptionStatus.INCOMPLETE.value,
        "subscription.halted": SubscriptionStatus.PAST_DUE.value,
        "subscription.cancelled": SubscriptionStatus.CANCELED.value,
        "subscription.completed": SubscriptionStatus.CANCELED.value,
    }

    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _entity(payload: dict[str, Any], name: str) -> dict[str, Any]:
        return payload.get("payload", {}).get(name, {}).get("entity", {}) or {}

    @staticmethod
    def _period(value: Any, fallback: str) -> str:
        """Normalize Razorpay epoch period values into persisted UTC ISO-8601."""
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
        return str(value or fallback)

    def process(self, event_id: str, payload: dict[str, Any]) -> dict[str, str]:
        event_type = str(payload.get("event", ""))
        if not event_type:
            raise ValueError("Missing Razorpay event type")
        if not self.database.claim_razorpay_webhook_event(event_id, event_type):
            return {"status": "duplicate", "event": event_type}
        if event_type not in self.ACTIVE_EVENTS and event_type not in self.INACTIVE_EVENTS:
            return {"status": "ignored", "event": event_type}

        payment = self._entity(payload, "payment")
        order = self._entity(payload, "order")
        subscription = self._entity(payload, "subscription")
        notes = subscription.get("notes") or order.get("notes") or payment.get("notes") or {}
        noted_user_id = notes.get("user_id")
        subscription_id = subscription.get("id")
        order_id = order.get("id") or payment.get("order_id")
        payment_id = payment.get("id")
        existing = next((self.database.get_subscription_by_razorpay_id(value) for value in (subscription_id, order_id, payment_id) if value), None)
        if existing and noted_user_id and noted_user_id != existing.user_id:
            return {"status": "rejected", "event": event_type}
        user_id = noted_user_id or (existing.user_id if existing else None)
        if not user_id or not self.database.get_user_by_id(user_id):
            return {"status": "unmatched", "event": event_type}

        plan = str(notes.get("plan_name", existing.plan_name if existing else "")).upper()
        if plan not in {tier.value for tier in (PlanTier.STARTER, PlanTier.PROFESSIONAL, PlanTier.ENTERPRISE)}:
            return {"status": "rejected", "event": event_type}
        yearly = str(notes.get("is_yearly", "false")).lower() == "true"
        now = datetime.now(timezone.utc).isoformat()
        status = SubscriptionStatus.ACTIVE.value if event_type in self.ACTIVE_EVENTS else self.INACTIVE_EVENTS[event_type]
        if event_type in {"payment.captured", "order.paid"} and payment.get("status") not in {None, "captured"}:
            return {"status": "ignored", "event": event_type}
        # Non-paid lifecycle notifications may only modify a subscription that
        # was already established by a verified paid event.
        if event_type in self.INACTIVE_EVENTS and existing is None:
            return {"status": "unmatched", "event": event_type}
        base = existing or UserSubscription(id=f"sub_{user_id[:12]}_{uuid4().hex[:6]}", user_id=user_id)
        base.razorpay_customer_id = subscription.get("customer_id") or payment.get("customer_id") or base.razorpay_customer_id
        base.razorpay_subscription_id = subscription_id or base.razorpay_subscription_id
        base.razorpay_order_id = order_id or base.razorpay_order_id
        base.razorpay_payment_id = payment_id or base.razorpay_payment_id
        base.plan_name, base.billing_cycle, base.subscription_status = plan, (BillingCycle.YEARLY.value if yearly else BillingCycle.MONTHLY.value), status
        base.cancel_at_period_end = event_type == "subscription.cancelled"
        base.current_period_start = self._period(subscription.get("current_start"), base.current_period_start or now)
        base.current_period_end = self._period(subscription.get("current_end"), base.current_period_end or now)
        if status == SubscriptionStatus.ACTIVE.value and not base.minimum_commitment_end:
            commitment_start = datetime.fromisoformat(base.current_period_start.replace("Z", "+00:00"))
            base.minimum_commitment_end = (commitment_start + timedelta(days=90)).isoformat()
        base.updated_at = now
        self.database.save_subscription(base)
        return {"status": "processed", "event": event_type}
