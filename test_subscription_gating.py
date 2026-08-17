import unittest
from uuid import uuid4
from database.database import Database
from models.user import User, UserRole
from models.subscription import UserSubscription, SubscriptionStatus, PlanTier
from core.security import (
    require_authenticated_user,
    require_active_subscription,
)
from core.billing.subscription_service import SubscriptionService


class TestSubscriptionGating(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.sub_svc = SubscriptionService(self.db)

    def test_unauthenticated_user_access_denied(self):
        ok, msg = require_authenticated_user(None)
        self.assertFalse(ok)
        self.assertIn("Authentication required", msg)

    def test_inactive_subscriber_access_denied_to_workspace(self):
        user = User(
            id="usr_free_1",
            name="Unpaid User",
            email="freeuser@gmail.com",
            password_hash="fakehash",
            role=UserRole.USER.value,
        )
        self.db.create_user(user)

        free_sub = UserSubscription(
            id="sub_free_1",
            user_id=user.id,
            plan_name=PlanTier.FREE.value,
            subscription_status=SubscriptionStatus.ACTIVE.value,
        )
        self.db.save_subscription(free_sub)

        ok, msg = require_active_subscription(user, free_sub)
        self.assertFalse(ok)
        self.assertIn("Active subscription required", msg)

    def test_active_paid_subscriber_access_granted(self):
        user = User(
            id="usr_pro_1",
            name="Pro Merchant",
            email="pro@retail.com",
            password_hash="fakehash",
            role=UserRole.USER.value,
        )
        self.db.create_user(user)

        pro_sub = UserSubscription(
            id="sub_pro_1",
            user_id=user.id,
            plan_name=PlanTier.PROFESSIONAL.value,
            subscription_status=SubscriptionStatus.ACTIVE.value,
        )
        self.db.save_subscription(pro_sub)

        ok, msg = require_active_subscription(user, pro_sub)
        self.assertTrue(ok)
        self.assertEqual(msg, "Subscription active")

    def test_admin_has_full_workspace_access(self):
        admin = User(
            id="usr_admin_1",
            name="Admin User",
            email="srivastavavardaan05@gmail.com",
            password_hash="fakehash",
            role=UserRole.ADMIN.value,
        )
        ok, msg = require_active_subscription(admin, None)
        self.assertTrue(ok)
        self.assertEqual(msg, "Admin authorized")


if __name__ == "__main__":
    unittest.main()
