"""Test Suite for Coupon & Promotional Discount Verification."""
import unittest
from core.billing.coupon_service import CouponService
from core.config import get_plan_pricing


class TestCouponService(unittest.TestCase):
    """Test coupon eligibility, plan restrictions, and discount math."""

    def test_valid_launch50_coupon(self):
        valid, msg, discount = CouponService.validate_coupon("LAUNCH50", "STARTER")
        self.assertTrue(valid)
        self.assertEqual(discount, 50.0)

        # Discount calculation
        final_price = CouponService.calculate_discounted_price(
            get_plan_pricing("STARTER")["monthly_usd"], "PERCENTAGE", discount
        )
        self.assertEqual(final_price, 9.50)

    def test_percentage_discounts_use_official_usd_base_prices(self):
        for plan, base_price, expected in (
            ("STARTER", 19.0, 15.20),
            ("PROFESSIONAL", 49.0, 39.20),
            ("ENTERPRISE", 149.0, 119.20),
        ):
            self.assertEqual(get_plan_pricing(plan)["monthly_usd"], base_price)
            self.assertEqual(
                CouponService.calculate_discounted_price(base_price, "PERCENTAGE", 20.0),
                expected,
            )

    def test_invalid_and_empty_coupon(self):
        valid, msg, _ = CouponService.validate_coupon("INVALID_CODE_XYZ", "STARTER")
        self.assertFalse(valid)
        self.assertIn("invalid", msg.lower())

        valid_empty, msg_e, _ = CouponService.validate_coupon("", "STARTER")
        self.assertFalse(valid_empty)

    def test_already_redeemed_coupon_rejection(self):
        valid, msg, _ = CouponService.validate_coupon("LAUNCH50", "STARTER", already_redeemed=True)
        self.assertFalse(valid)
        self.assertIn("already redeemed", msg.lower())

    def test_plan_specific_coupon_restriction(self):
        # STARTER100 is only valid for STARTER plan
        valid_st, _, _ = CouponService.validate_coupon("STARTER100", "STARTER")
        self.assertTrue(valid_st)

        valid_pro, msg_p, _ = CouponService.validate_coupon("STARTER100", "PROFESSIONAL")
        self.assertFalse(valid_pro)
        self.assertIn("only valid for starter", msg_p.lower())


if __name__ == "__main__":
    unittest.main()
