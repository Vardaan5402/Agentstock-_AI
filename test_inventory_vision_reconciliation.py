"""Automated Unit Tests for Camera Inventory Vision & Discrepancy Reconciliation."""

import os
import unittest
from uuid import uuid4
from database.database import Database
from models.business import Business
from models.inventory import Product
from models.inventory_capture import (
    InventoryVisionResult,
    InventoryVisionItem,
    ReconciliationItemStatus,
)
from core.inventory_reconciliation import InventoryReconciliationEngine
from core.billing.subscription_service import SubscriptionService


class TestInventoryVisionReconciliation(unittest.TestCase):
    """Test vision structured extraction, discrepancy calculations, batch reconciliation, and entitlements."""

    def setUp(self):
        self.test_db_path = f"test_recon_{uuid4().hex[:8]}.db"
        self.database = Database(self.test_db_path)
        self.database.init_db()

        self.business = Business(
            id="biz_test",
            name="Test Retailer",
            country="India",
            currency="INR",
            industry="Retail",
            inventory_budget=100000.0,
        )
        self.database.create_business(self.business)

        self.p1 = Product(
            id="prod_coke_1",
            business_id="biz_test",
            sku="COKE500",
            name="Coca Cola 500ml",
            current_stock=42,
            unit_cost=30.0,
            daily_demand=10.0,
            safety_stock=15,
        )
        self.p2 = Product(
            id="prod_pepsi_1",
            business_id="biz_test",
            sku="PEPSI500",
            name="Pepsi 500ml",
            current_stock=18,
            unit_cost=28.0,
            daily_demand=6.0,
            safety_stock=10,
        )
        self.p3 = Product(
            id="prod_sprite_1",
            business_id="biz_test",
            sku="SPR500",
            name="Sprite 500ml",
            current_stock=12,
            unit_cost=25.0,
            daily_demand=4.0,
            safety_stock=8,
        )
        self.database.create_product(self.p1)
        self.database.create_product(self.p2)
        self.database.create_product(self.p3)

        self.engine = InventoryReconciliationEngine(self.database)

    def tearDown(self):
        self.database.close()
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

    def test_vision_result_no_hallucination_null_quantity(self):
        """Ensure unquantifiable items preserve null observed_quantity rather than inventing 0."""
        item = InventoryVisionItem(
            product_name="Sprite 500ml",
            sku="SPR500",
            observed_quantity=None,
            evidence="Partially hidden bottles, count cannot be determined with certainty.",
        )
        self.assertIsNone(item.observed_quantity)

        res = InventoryVisionResult(
            items=[item],
            image_hash="hash_123",
            model="gemini-2.5-flash",
        )
        self.assertEqual(len(res.items), 1)
        self.assertIsNone(res.items[0].observed_quantity)

    def test_reconciliation_discrepancy_report_generation(self):
        """Test generating report with Deficit (-5), Match (0), and Unquantifiable items."""
        vision_res = InventoryVisionResult(
            items=[
                InventoryVisionItem(
                    product_name="Coca Cola 500ml",
                    sku="COKE500",
                    observed_quantity=37, # System has 42 -> Deficit of -5
                    confidence=0.96,
                ),
                InventoryVisionItem(
                    product_name="Pepsi 500ml",
                    sku="PEPSI500",
                    observed_quantity=18, # System has 18 -> Match of 0
                    confidence=0.94,
                ),
                InventoryVisionItem(
                    product_name="Sprite 500ml",
                    sku="SPR500",
                    observed_quantity=None, # Unquantifiable
                    confidence=0.60,
                ),
            ],
            image_hash="img_hash_abc",
        )

        report = self.engine.generate_report(vision_res)
        self.assertEqual(report.total_detected, 3)
        self.assertEqual(report.total_discrepancies, 1) # Coke has -5
        self.assertEqual(report.total_matched, 1) # Pepsi is match

        items = {it.detected_sku: it for it in report.items}

        # Check Coke deficit
        coke_item = items.get("COKE500")
        self.assertIsNotNone(coke_item)
        self.assertEqual(coke_item.status, ReconciliationItemStatus.DEFICIT)
        self.assertEqual(coke_item.discrepancy, -5)
        self.assertEqual(coke_item.system_stock, 42)
        self.assertEqual(coke_item.observed_quantity, 37)

        # Check Pepsi match
        pepsi_item = items.get("PEPSI500")
        self.assertIsNotNone(pepsi_item)
        self.assertEqual(pepsi_item.status, ReconciliationItemStatus.MATCH)
        self.assertEqual(pepsi_item.discrepancy, 0)

        # Check Sprite unquantifiable
        sprite_item = items.get("SPR500")
        self.assertIsNotNone(sprite_item)
        self.assertEqual(sprite_item.status, ReconciliationItemStatus.UNQUANTIFIABLE)

    def test_apply_reconciliation_batch_update_and_audit(self):
        """Test applying reconciliation update to selected item and verifying database & audit event."""
        vision_res = InventoryVisionResult(
            items=[
                InventoryVisionItem(
                    product_name="Coca Cola 500ml",
                    sku="COKE500",
                    observed_quantity=37,
                ),
            ],
            image_hash="img_hash_reconcile_test",
        )
        report = self.engine.generate_report(vision_res)
        item_id = report.items[0].item_id

        # Apply update
        res = self.engine.apply_reconciliation(report, [item_id], user_id="test_user_1")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["adjusted_count"], 1)

        # Verify product stock updated in database
        updated_prod = self.database.get_product(self.p1.id)
        self.assertEqual(updated_prod.current_stock, 37)

        # Verify audit event logged
        audits = self.database.list_audit_events()
        self.assertTrue(any(a["event_type"] == "INVENTORY_CAMERA_RECONCILIATION" for a in audits))

    def test_subscription_entitlements_for_voice_and_vision(self):
        """Verify tier entitlements and scan quotas in SubscriptionService."""
        sub_svc = SubscriptionService(self.database)

        # Free tier entitlements
        voice_lim_free = sub_svc.get_voice_limits("user_free")
        self.assertEqual(voice_lim_free["monthly_commands"], 25)

        vision_lim_free = sub_svc.get_vision_limits("user_free")
        self.assertEqual(vision_lim_free["monthly_scans"], 10)

        self.assertTrue(sub_svc.has_feature("user_free", "voice_inventory"))
        self.assertTrue(sub_svc.has_feature("user_free", "vision_inventory_scan"))


if __name__ == "__main__":
    unittest.main()
