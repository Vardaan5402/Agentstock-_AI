"""Test Suite for Supplier Management, PO Drafting, WhatsApp URL, and Communication Logs."""
import os
import unittest
from database.database import Database
from models.business import Business
from models.supplier import Supplier
from models.communication import CommType, CommStatus
from core.supplier_communication import SupplierCommunicationService


class TestSupplierCommunication(unittest.TestCase):
    """Test purchase order drafting, WhatsApp deep link generation, and communication logging."""

    def setUp(self):
        self.db_path = "test_supplier_comm.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.database = Database(self.db_path)
        self.comm_service = SupplierCommunicationService(self.database)

        # Create business and supplier
        self.biz = Business(
            id="biz_test_01",
            user_id="usr_owner",
            name="Apex Retail Co",
            country="IN",
            currency="INR",
            industry="Retail",
            inventory_budget=50000.0,
        )
        self.database.create_business(self.biz)

        self.sup = Supplier(
            id="sup_test_01",
            business_id="biz_test_01",
            user_id="usr_owner",
            name="Ramesh Supplies",
            company_name="Ramesh Wholesale Traders",
            phone="+91 9876543210",
            email="ramesh@wholesale.com",
            lead_time_days=2.0,
            reliability_score=0.95,
        )
        self.database.create_supplier(self.sup)

    def tearDown(self):
        self.database.close()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_generate_order_draft(self):
        draft = self.comm_service.generate_order_draft(
            business_name="Apex Retail Co",
            supplier=self.sup,
            product_name="Basmati Rice 5kg",
            sku="RICE-5KG",
            quantity=50,
            unit_price=320.0,
            total_cost=16000.0,
            notes="Please deliver before 11 AM",
        )
        self.assertTrue(draft.order_id.startswith("PO-"))
        self.assertIn("Apex Retail Co", draft.formatted_body)
        self.assertIn("Basmati Rice 5kg", draft.formatted_body)
        self.assertIn("₹16,000.00", draft.formatted_body)
        self.assertIn("Please deliver before 11 AM", draft.formatted_body)

    def test_whatsapp_and_phone_links(self):
        wa_url = self.comm_service.get_whatsapp_url("+91 9876543210", "Hello Ramesh, sending PO")
        self.assertTrue(wa_url.startswith("https://wa.me/919876543210?text=Hello%20Ramesh%2C%20sending%20PO"))

        tel_url = self.comm_service.get_phone_call_url("+91 9876543210")
        self.assertEqual(tel_url, "tel:+919876543210")

    def test_record_and_list_communications(self):
        self.comm_service.record_communication(
            business_id="biz_test_01",
            user_id="usr_owner",
            supplier_id="sup_test_01",
            comm_type=CommType.WHATSAPP,
            body="Purchase order PO-2026-001 sent via WhatsApp",
            order_reference="PO-2026-001",
            recipient="+91 9876543210",
        )
        comms = self.database.list_supplier_communications(business_id="biz_test_01")
        self.assertEqual(len(comms), 1)
        self.assertEqual(comms[0].comm_type, "WHATSAPP")
        self.assertEqual(comms[0].order_reference, "PO-2026-001")

    def test_supplier_soft_delete_and_restore(self):
        # Initial active
        active_list = self.database.list_suppliers("biz_test_01", include_archived=False)
        self.assertEqual(len(active_list), 1)

        # Archive
        self.database.archive_supplier("sup_test_01")
        active_after_arc = self.database.list_suppliers("biz_test_01", include_archived=False)
        self.assertEqual(len(active_after_arc), 0)

        # Include archived
        all_list = self.database.list_suppliers("biz_test_01", include_archived=True)
        self.assertEqual(len(all_list), 1)
        self.assertTrue(all_list[0].is_archived)

        # Restore
        self.database.restore_supplier("sup_test_01")
        restored = self.database.list_suppliers("biz_test_01", include_archived=False)
        self.assertEqual(len(restored), 1)
        self.assertFalse(restored[0].is_archived)


if __name__ == "__main__":
    unittest.main()
