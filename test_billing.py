"""Automated Unit & Integration Tests for Stripe Billing & Subscriptions."""
import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from database.database import Database
from models.user import User
from models.subscription import UserSubscription, SubscriptionStatus, PlanTier
from core.billing.stripe_service import StripeBillingService
from core.billing.subscription_service import SubscriptionService
from core.billing.webhook_service import StripeWebhookHandler
from core.config import get_stripe_price_id, get_app_base_url


class TestStripeBilling(unittest.TestCase):
    """Test suite for Stripe payments, webhook processing, and entitlement controls."""

    def setUp(self):
        self.test_db_path = f"test_billing_{uuid4().hex[:8]}.db"
        self.database = Database(self.test_db_path)
        self.database.init_db()

        self.user = User(
            id=uuid4().hex,
            name="Alex Mercer",
            email="alex@retailer.com",
            password_hash="testhash123",
            is_verified=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.database.create_user(self.user)

    def tearDown(self):
        self.database.close()
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

    def test_subscription_model_properties(self):
        """Verify active status calculations on UserSubscription model."""
        sub_active = UserSubscription(
            id="sub_1",
            user_id=self.user.id,
            plan_name=PlanTier.PROFESSIONAL.value,
            subscription_status=SubscriptionStatus.ACTIVE.value,
        )
        self.assertTrue(sub_active.is_active)

        sub_canceled = UserSubscription(
            id="sub_2",
            user_id=self.user.id,
            plan_name=PlanTier.PROFESSIONAL.value,
            subscription_status=SubscriptionStatus.CANCELED.value,
        )
        self.assertFalse(sub_canceled.is_active)

    def test_database_subscription_crud_and_idempotency(self):
        """Test creating, retrieving, and updating subscriptions idempotently."""
        sub = UserSubscription(
            id="sub_test_id",
            user_id=self.user.id,
            stripe_customer_id="cus_12345",
            stripe_subscription_id="sub_12345",
            stripe_price_id="price_pro_monthly",
            plan_name=PlanTier.PROFESSIONAL.value,
            subscription_status=SubscriptionStatus.ACTIVE.value,
        )
        self.database.save_subscription(sub)

        # Retrieval checks
        fetched = self.database.get_subscription_by_user_id(self.user.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.plan_name, "PROFESSIONAL")
        self.assertEqual(fetched.stripe_customer_id, "cus_12345")

        by_cust = self.database.get_subscription_by_stripe_customer_id("cus_12345")
        self.assertEqual(by_cust.id, "sub_test_id")

        by_sub = self.database.get_subscription_by_stripe_subscription_id("sub_12345")
        self.assertEqual(by_sub.id, "sub_test_id")

        # Idempotent update
        sub.subscription_status = SubscriptionStatus.CANCELED.value
        self.database.save_subscription(sub)

        updated = self.database.get_subscription_by_user_id(self.user.id)
        self.assertEqual(updated.subscription_status, "canceled")

    def test_entitlement_service_access_control(self):
        """Test centralized entitlement checks for Free vs Pro tiers."""
        sub_svc = SubscriptionService(self.database)

        # Free tier user (default)
        plan_free = sub_svc.get_user_plan(self.user.id)
        self.assertEqual(plan_free, "FREE")
        self.assertTrue(sub_svc.has_feature(self.user.id, "deterministic_simulation"))
        self.assertFalse(sub_svc.has_feature(self.user.id, "custom_policy_engine"))

        # Upgrade to Enterprise
        sub_ent = UserSubscription(
            id="sub_ent_1",
            user_id=self.user.id,
            plan_name=PlanTier.ENTERPRISE.value,
            subscription_status=SubscriptionStatus.ACTIVE.value,
        )
        self.database.save_subscription(sub_ent)

        plan_ent = sub_svc.get_user_plan(self.user.id)
        self.assertEqual(plan_ent, "ENTERPRISE")
        self.assertTrue(sub_svc.has_feature(self.user.id, "custom_policy_engine"))
        can_adv, msg = sub_svc.can_use_advanced_features(self.user.id)
        self.assertTrue(can_adv)

    def test_stripe_service_mock_checkout_session(self):
        """Verify checkout session generator produces valid URLs in test/mock mode."""
        stripe_svc = StripeBillingService(secret_key="sk_test_placeholder_key")
        session = stripe_svc.create_checkout_session(
            user_id=self.user.id,
            user_email=self.user.email,
            plan_name="PROFESSIONAL",
            is_yearly=True,
        )
        self.assertIn("url", session)
        self.assertIn("plan=PROFESSIONAL", session["url"])
        self.assertEqual(session["mode"], "mock")

    def test_webhook_checkout_completed(self):
        """Verify webhook handler saves active subscription on checkout.session.completed."""
        handler = StripeWebhookHandler(self.database)
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_999",
                    "customer": "cus_stripe_111",
                    "subscription": "sub_stripe_222",
                    "metadata": {
                        "user_id": self.user.id,
                        "plan_name": "PROFESSIONAL",
                    },
                }
            },
        }
        res = handler.handle_event(event)
        self.assertEqual(res["status"], "success")

        sub = self.database.get_subscription_by_user_id(self.user.id)
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan_name, "PROFESSIONAL")
        self.assertEqual(sub.subscription_status, "active")

        # Verify audit event logged
        events = self.database.list_audit_events()
        self.assertTrue(any(e["event_type"] == "SUBSCRIPTION_CHECKOUT_COMPLETED" for e in events))

    def test_webhook_subscription_canceled(self):
        """Verify customer.subscription.deleted marks status canceled in database."""
        # Seed active subscription
        sub = UserSubscription(
            id="sub_active_test",
            user_id=self.user.id,
            stripe_customer_id="cus_test_cancel",
            stripe_subscription_id="sub_test_cancel",
            plan_name=PlanTier.PROFESSIONAL.value,
            subscription_status=SubscriptionStatus.ACTIVE.value,
        )
        self.database.save_subscription(sub)

        handler = StripeWebhookHandler(self.database)
        event = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test_cancel",
                    "customer": "cus_test_cancel",
                }
            },
        }
        res = handler.handle_event(event)
        self.assertEqual(res["status"], "success")

        updated = self.database.get_subscription_by_user_id(self.user.id)
        self.assertEqual(updated.subscription_status, "canceled")

    def test_webhook_invoice_paid_audit(self):
        """Verify invoice.paid generates audit trail event."""
        handler = StripeWebhookHandler(self.database)
        event = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "inv_12345",
                    "customer": "cus_test_cust",
                    "amount_paid": 199900,
                    "currency": "inr",
                }
            },
        }
        res = handler.handle_event(event)
        self.assertEqual(res["status"], "success")

        events = self.database.list_audit_events()
        self.assertTrue(any(e["event_type"] == "PAYMENT_SUCCEEDED" for e in events))


if __name__ == "__main__":
    unittest.main()
