import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from database.database import Database
from models.user import User, UserRole
from core.security import hash_password
from core.billing.razorpay_service import RazorpayBillingService
import razorpay_webhook


class TestRazorpayWebhook(unittest.TestCase):
    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_file.close()
        self.db = Database(self.db_file.name)
        self.db.create_user(User(id="usr_webhook", name="Webhook User", email="webhook@example.com", password_hash=hash_password("SafePass123!"), role=UserRole.USER.value))
        self.service = RazorpayBillingService(key_id="rzp_test", key_secret="secret", webhook_secret="webhook-secret")
        self.client_patch = patch.object(razorpay_webhook, "Database", return_value=self.db)
        self.service_patch = patch.object(razorpay_webhook, "RazorpayBillingService", return_value=self.service)
        self.client_patch.start(); self.service_patch.start()
        self.client = TestClient(razorpay_webhook.app)

    def tearDown(self):
        self.service_patch.stop(); self.client_patch.stop(); self.db.close()

    def _post(self, event, event_id="evt_1", user_id="usr_webhook", plan="STARTER", period_start=1735689600, period_end=1738281600):
        notes = {"user_id":user_id, "plan_name":plan, "is_yearly":"false"}
        payload = {"event": event, "payload": {"payment": {"entity": {"id":"pay_1", "order_id":"order_1", "status":"captured", "notes":notes}}, "order":{"entity":{"id":"order_1", "notes":notes}}, "subscription":{"entity":{"id":"sub_1", "customer_id":"cust_1", "current_start":period_start, "current_end":period_end, "notes":notes}}}}
        raw = json.dumps(payload).encode()
        return self.client.post("/api/razorpay/webhook", content=raw, headers={"X-Razorpay-Signature": self.service.generate_mock_webhook_signature(raw), "X-Razorpay-Event-Id": event_id})

    def test_signature_and_lifecycle_events(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.post("/api/razorpay/webhook", content=b"{}").status_code, 400)
        self.assertEqual(self.client.post("/api/razorpay/webhook", content=b"{}", headers={"X-Razorpay-Signature":"bad"}).status_code, 401)
        self.assertEqual(self.client.post("/api/razorpay/webhook", content=b"not-json", headers={"X-Razorpay-Signature":self.service.generate_mock_webhook_signature(b"not-json")}).status_code, 400)
        self.assertEqual(self._post("payment.captured").json()["status"], "processed")
        self.assertEqual(self._post("payment.captured").json()["status"], "duplicate")
        self.assertEqual(self.db.get_subscription_by_user_id("usr_webhook").subscription_status, "active")
        self.assertIsNotNone(self.db.get_subscription_by_user_id("usr_webhook").minimum_commitment_end)
        self.assertEqual(self._post("order.paid", "evt_order").json()["status"], "processed")
        self.assertEqual(self._post("subscription.activated", "evt_activation").json()["status"], "processed")
        self.assertEqual(self._post("payment.failed", "evt_2").json()["status"], "processed")
        self.assertEqual(self.db.get_subscription_by_user_id("usr_webhook").subscription_status, "past_due")
        self.assertEqual(self._post("subscription.charged", "evt_3").json()["status"], "processed")
        self.assertEqual(self.db.get_subscription_by_user_id("usr_webhook").subscription_status, "active")
        self.assertIn("T", self.db.get_subscription_by_user_id("usr_webhook").current_period_start)
        self.assertEqual(self._post("subscription.pending", "evt_pending").json()["status"], "processed")
        self.assertEqual(self.db.get_subscription_by_user_id("usr_webhook").subscription_status, "incomplete")
        self.assertEqual(self._post("subscription.halted", "evt_halted").json()["status"], "processed")
        self.assertEqual(self.db.get_subscription_by_user_id("usr_webhook").subscription_status, "past_due")
        self.assertEqual(self._post("subscription.cancelled", "evt_4").json()["status"], "processed")
        self.assertEqual(self.db.get_subscription_by_user_id("usr_webhook").subscription_status, "canceled")
        self.assertEqual(self._post("subscription.completed", "evt_completed").json()["status"], "processed")
        self.assertEqual(self._post("unsupported.event", "evt_5").json()["status"], "ignored")

    def test_rejects_wrong_user_and_invalid_plan(self):
        self.assertEqual(self._post("payment.captured", "evt_good").json()["status"], "processed")
        self.assertEqual(self._post("subscription.charged", "evt_cross", user_id="usr_other").json()["status"], "rejected")
        self.assertEqual(self._post("payment.captured", "evt_badplan", plan="ADMIN").json()["status"], "rejected")
        self.assertEqual(self._post("subscription.pending", "evt_unknown", user_id="missing").json()["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
