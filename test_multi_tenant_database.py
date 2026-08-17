"""Test Suite for Multi-Tenant Database Isolation, IDOR Prevention, and GDPR Compliance."""
import os
import unittest
from database.database import Database
from models.user import User, UserRole
from models.business import Business
from models.inventory import Product
from models.supplier import Supplier
from core.security import verify_tenant_ownership


class TestMultiTenantDatabase(unittest.TestCase):
    """Test tenant isolation, cross-tenant IDOR checks, GDPR export, and account deletion."""

    def setUp(self):
        self.db_path = "test_multi_tenant.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.database = Database(self.db_path)

        # Tenant A (Owner 1)
        self.user_a = User(id="usr_tenant_a", name="Alice", email="alice@store.com", password_hash="hash_a", role="USER")
        self.database.create_user(self.user_a)
        self.biz_a = Business(id="biz_a", user_id="usr_tenant_a", name="Alice Store", country="IN", currency="INR", industry="Retail", inventory_budget=10000.0)
        self.database.create_business(self.biz_a)
        self.prod_a = Product(id="prod_a", business_id="biz_a", user_id="usr_tenant_a", sku="SKU-A", name="Product A", current_stock=100, unit_cost=10.0, daily_demand=2.0, safety_stock=10)
        self.database.create_product(self.prod_a)

        # Tenant B (Owner 2)
        self.user_b = User(id="usr_tenant_b", name="Bob", email="bob@store.com", password_hash="hash_b", role="USER")
        self.database.create_user(self.user_b)
        self.biz_b = Business(id="biz_b", user_id="usr_tenant_b", name="Bob Store", country="IN", currency="INR", industry="Retail", inventory_budget=20000.0)
        self.database.create_business(self.biz_b)

    def tearDown(self):
        self.database.close()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_tenant_isolation_in_listings(self):
        # Alice only sees Alice's businesses
        alice_bizs = self.database.list_businesses(user_id="usr_tenant_a")
        self.assertEqual(len(alice_bizs), 1)
        self.assertEqual(alice_bizs[0].id, "biz_a")

        # Bob only sees Bob's businesses
        bob_bizs = self.database.list_businesses(user_id="usr_tenant_b")
        self.assertEqual(len(bob_bizs), 1)
        self.assertEqual(bob_bizs[0].id, "biz_b")

    def test_cross_tenant_idor_ownership_verification(self):
        # Alice accessing own resource -> Allowed
        self.assertTrue(verify_tenant_ownership("usr_tenant_a", "usr_tenant_a"))

        # Bob attempting to access Alice's resource -> Blocked
        self.assertFalse(verify_tenant_ownership("usr_tenant_b", "usr_tenant_a"))

        # Platform Admin accessing any resource -> Allowed
        self.assertTrue(verify_tenant_ownership("usr_admin", "usr_tenant_a", is_admin=True))

    def test_gdpr_data_export(self):
        export = self.database.export_user_data("usr_tenant_a")
        self.assertEqual(export["user_profile"]["email"], "alice@store.com")
        self.assertEqual(len(export["businesses"]), 1)
        self.assertEqual(len(export["products"]), 1)
        self.assertNotIn("password_hash", export["user_profile"])

    def test_gdpr_account_data_deletion(self):
        self.database.delete_user_account_data("usr_tenant_a")

        # User and catalog items must be deleted
        self.assertIsNone(self.database.get_user_by_id("usr_tenant_a"))
        self.assertEqual(len(self.database.list_products("biz_a")), 0)
        self.assertIsNone(self.database.get_business("biz_a"))


if __name__ == "__main__":
    unittest.main()
