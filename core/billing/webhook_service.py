"""Stripe Webhook Event Handler for AgentStock AI."""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import uuid4
from database.database import Database
from models.subscription import UserSubscription, SubscriptionStatus, PlanTier
from models.persistence import AuditEventType
from core.decision_persistence import save_raw_audit_event


class StripeWebhookHandler:
    """Processes verified Stripe webhook events and updates subscription state idempotently."""

    def __init__(self, database: Database):
        self.database = database

    def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch event based on Stripe event type."""
        event_type = event.get("type", "")
        data_object = event.get("data", {}).get("object", {})

        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.subscription.created": self._handle_subscription_updated,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_invoice_payment_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            return handler(data_object, event_type)

        return {"status": "ignored", "event_type": event_type}

    def _handle_checkout_completed(self, session: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """Handle checkout.session.completed."""
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        plan_name = metadata.get("plan_name", PlanTier.STARTER.value).upper()
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")

        if not user_id:
            existing = self.database.get_subscription_by_stripe_customer_id(customer_id) if customer_id else None
            user_id = existing.user_id if existing else "unknown_user"

        sub_id = f"sub_{user_id[:12]}"
        existing = self.database.get_subscription_by_user_id(user_id)
        if existing:
            sub_id = existing.id

        subscription = UserSubscription(
            id=sub_id,
            user_id=user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            plan_name=plan_name,
            subscription_status=SubscriptionStatus.ACTIVE.value,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self.database.save_subscription(subscription)

        save_raw_audit_event(
            self.database,
            entity_type="user_subscription",
            entity_id=subscription.id,
            event_type=AuditEventType.SUBSCRIPTION_CHECKOUT_COMPLETED,
            metadata={"plan": plan_name, "user_id": user_id, "customer_id": str(customer_id)},
        )
        return {"status": "success", "action": "checkout_completed", "user_id": user_id, "plan": plan_name}

    def _handle_subscription_updated(self, sub_obj: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """Handle customer.subscription.created / customer.subscription.updated."""
        stripe_sub_id = sub_obj.get("id")
        customer_id = sub_obj.get("customer")
        status = sub_obj.get("status", SubscriptionStatus.ACTIVE.value)
        cancel_at_period_end = bool(sub_obj.get("cancel_at_period_end", False))
        
        # Period timestamps
        period_start = sub_obj.get("current_period_start")
        period_end = sub_obj.get("current_period_end")
        start_iso = datetime.fromtimestamp(period_start, tz=timezone.utc).isoformat() if period_start else None
        end_iso = datetime.fromtimestamp(period_end, tz=timezone.utc).isoformat() if period_end else None

        # Price & Plan
        items = sub_obj.get("items", {}).get("data", [])
        price_id = items[0].get("price", {}).get("id") if items else None
        
        # Metadata or existing lookup
        metadata = sub_obj.get("metadata", {})
        user_id = metadata.get("user_id")
        plan_name = metadata.get("plan_name", PlanTier.PROFESSIONAL.value).upper()

        if not user_id:
            existing = self.database.get_subscription_by_stripe_subscription_id(stripe_sub_id) or \
                       self.database.get_subscription_by_stripe_customer_id(customer_id)
            if existing:
                user_id = existing.user_id
                plan_name = existing.plan_name
            else:
                user_id = "unknown_user"

        sub_id = f"sub_{user_id[:12]}"
        existing = self.database.get_subscription_by_user_id(user_id)
        if existing:
            sub_id = existing.id

        subscription = UserSubscription(
            id=sub_id,
            user_id=user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=stripe_sub_id,
            stripe_price_id=price_id,
            plan_name=plan_name,
            subscription_status=status,
            current_period_start=start_iso,
            current_period_end=end_iso,
            cancel_at_period_end=cancel_at_period_end,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self.database.save_subscription(subscription)

        save_raw_audit_event(
            self.database,
            entity_type="user_subscription",
            entity_id=subscription.id,
            event_type=AuditEventType.SUBSCRIPTION_STATUS_UPDATED,
            metadata={"status": status, "plan": plan_name, "user_id": user_id},
        )
        return {"status": "success", "action": "subscription_updated", "subscription_id": stripe_sub_id}

    def _handle_subscription_deleted(self, sub_obj: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """Handle customer.subscription.deleted."""
        stripe_sub_id = sub_obj.get("id")
        customer_id = sub_obj.get("customer")

        existing = self.database.get_subscription_by_stripe_subscription_id(stripe_sub_id) or \
                   self.database.get_subscription_by_stripe_customer_id(customer_id)

        if existing:
            existing.subscription_status = SubscriptionStatus.CANCELED.value
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            self.database.save_subscription(existing)

            save_raw_audit_event(
                self.database,
                entity_type="user_subscription",
                entity_id=existing.id,
                event_type=AuditEventType.SUBSCRIPTION_CANCELED,
                metadata={"user_id": existing.user_id, "subscription_id": str(stripe_sub_id)},
            )
            return {"status": "success", "action": "subscription_canceled", "user_id": existing.user_id}

        return {"status": "not_found", "subscription_id": stripe_sub_id}

    def _handle_invoice_paid(self, invoice: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """Handle invoice.paid."""
        customer_id = invoice.get("customer")
        amount_paid = invoice.get("amount_paid", 0) / 100.0
        currency = invoice.get("currency", "inr").upper()

        save_raw_audit_event(
            self.database,
            entity_type="invoice",
            entity_id=invoice.get("id", "inv_unknown"),
            event_type=AuditEventType.PAYMENT_SUCCEEDED,
            metadata={"customer_id": str(customer_id), "amount": str(amount_paid), "currency": currency},
        )
        return {"status": "success", "action": "invoice_paid", "customer_id": customer_id}

    def _handle_invoice_payment_failed(self, invoice: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """Handle invoice.payment_failed."""
        customer_id = invoice.get("customer")
        save_raw_audit_event(
            self.database,
            entity_type="invoice",
            entity_id=invoice.get("id", "inv_unknown"),
            event_type=AuditEventType.PAYMENT_FAILED,
            metadata={"customer_id": str(customer_id), "attempt_count": str(invoice.get("attempt_count"))},
        )
        return {"status": "success", "action": "invoice_payment_failed", "customer_id": customer_id}
