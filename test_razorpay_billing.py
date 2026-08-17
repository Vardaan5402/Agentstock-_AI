"""Test Suite for Razorpay Subscription Billing & Webhook Signature Verification."""
import unittest
from unittest.mock import Mock, patch
from core.billing.razorpay_service import RazorpayBillingService


class TestRazorpayBilling(unittest.TestCase):
    """Test Razorpay order creation, HMAC-SHA256 verification, and sandbox operations."""

    def setUp(self):
        self.service = RazorpayBillingService(
            key_id="rzp_test_mock123",
            key_secret="mock_secret_key_456",
            webhook_secret="mock_webhook_secret_789",
        )

    @patch("core.billing.razorpay_service.requests.post")
    def test_create_order_monthly_and_yearly(self, mock_post):
        mock_response = Mock(status_code=200)
        mock_response.json.side_effect = [
            {"id": "order_monthly", "status": "created", "amount": 1900, "currency": "USD"},
            {"id": "order_yearly", "status": "created", "amount": 23400, "currency": "USD"},
        ]
        mock_post.return_value = mock_response
        # Monthly Starter
        order_m = self.service.create_order(
            user_id="usr_001",
            user_email="owner@store.com",
            plan_name="STARTER",
            is_yearly=False,
        )
        self.assertEqual(order_m["id"], "order_monthly")
        self.assertEqual(order_m["amount"], 1900)  # USD cents
        self.assertEqual(order_m["currency"], "USD")

        # Yearly Professional with Discount
        order_y = self.service.create_order(
            user_id="usr_002",
            user_email="pro@brand.com",
            plan_name="PROFESSIONAL",
            is_yearly=True,
            discount_amount=50.0,  # 50% off
        )
        self.assertEqual(order_y["id"], "order_yearly")
        expected_amount = int((39 * 12 * 0.5) * 100)
        self.assertEqual(order_y["amount"], expected_amount)

    def test_payment_signature_verification_valid_and_invalid(self):
        order_id = "order_test_987"
        payment_id = "pay_test_654"

        # Generate valid mock signature
        valid_sig = self.service.generate_mock_payment_signature(order_id, payment_id)
        self.assertTrue(self.service.verify_payment_signature(order_id, payment_id, valid_sig))

        # Tampered signature must fail
        tampered_sig = valid_sig[:-4] + "ffff"
        self.assertFalse(self.service.verify_payment_signature(order_id, payment_id, tampered_sig))

    def test_webhook_signature_verification(self):
        payload = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_123"}}}}'
        valid_wh_sig = self.service.generate_mock_webhook_signature(payload)
        self.assertTrue(self.service.verify_webhook_signature(payload, valid_wh_sig))

        # Modified payload must fail
        tampered_payload = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_FAKE"}}}}'
        self.assertFalse(self.service.verify_webhook_signature(tampered_payload, valid_wh_sig))


if __name__ == "__main__":
    unittest.main()
