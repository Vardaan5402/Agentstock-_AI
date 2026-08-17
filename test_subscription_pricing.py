"""Official customer-facing subscription pricing tests."""
import unittest

from core.config import get_plan_pricing


class TestSubscriptionPricing(unittest.TestCase):
    def test_official_monthly_usd_prices(self):
        self.assertEqual(get_plan_pricing("STARTER")["monthly_usd"], 19.0)
        self.assertEqual(get_plan_pricing("PROFESSIONAL")["monthly_usd"], 49.0)
        self.assertEqual(get_plan_pricing("ENTERPRISE")["monthly_usd"], 149.0)

    def test_legacy_inr_prices_are_not_active_configuration(self):
        for plan in ("STARTER", "PROFESSIONAL", "ENTERPRISE"):
            pricing = get_plan_pricing(plan)
            self.assertEqual(pricing["currency"], "USD")
            self.assertNotIn("monthly_inr", pricing)
            self.assertNotIn("yearly_inr", pricing)


if __name__ == "__main__":
    unittest.main()
