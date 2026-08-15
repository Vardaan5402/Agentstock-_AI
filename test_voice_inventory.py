"""Automated Unit Tests for Voice Inventory Assistant."""

import os
import unittest
from uuid import uuid4
from database.database import Database
from models.business import Business
from models.inventory import Product
from models.inventory_capture import (
    InventoryVoiceCommand,
    InventoryVoiceCommandType,
)
from core.voice_inventory import VoiceInventoryParser, _replace_number_words


class TestVoiceInventory(unittest.TestCase):
    """Test natural language parsing, confirmation safety, and atomic inventory mutations."""

    def setUp(self):
        self.test_db_path = f"test_voice_{uuid4().hex[:8]}.db"
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

        self.product = Product(
            id="prod_coke_test",
            business_id="biz_test",
            sku="COKE500",
            name="Coca Cola 500ml",
            current_stock=42,
            unit_cost=30.0,
            daily_demand=10.0,
            safety_stock=15,
        )
        self.database.create_product(self.product)
        self.parser = VoiceInventoryParser()

    def tearDown(self):
        self.database.close()
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

    def test_word_to_number_normalization(self):
        """Verify English number words are replaced with digits."""
        res = _replace_number_words("Add twenty five units of Coca Cola")
        self.assertEqual(res, "add 25 units of coca cola")

    def test_parse_add_stock(self):
        """Parse ADD_STOCK command with positive quantity."""
        cmd = self.parser.parse("Add 25 units of Coca Cola 500ml")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.ADD_STOCK)
        self.assertEqual(cmd.quantity, 25)
        self.assertTrue(cmd.requires_confirmation)
        self.assertIn("coca cola 500ml", cmd.product_identifier.lower())

    def test_parse_remove_stock(self):
        """Parse REMOVE_STOCK command."""
        cmd = self.parser.parse("Remove 5 units of SKU COKE500")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.REMOVE_STOCK)
        self.assertEqual(cmd.quantity, 5)
        self.assertTrue(cmd.requires_confirmation)

    def test_parse_set_stock(self):
        """Parse SET_STOCK command."""
        cmd = self.parser.parse("Set the stock of Coca Cola 500ml to 100")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.SET_STOCK)
        self.assertEqual(cmd.quantity, 100)
        self.assertTrue(cmd.requires_confirmation)

    def test_parse_query_stock(self):
        """Parse QUERY_STOCK command (read-only, does not require destructive confirmation)."""
        cmd = self.parser.parse("What's the current stock of SKU COKE500?")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.QUERY_STOCK)
        self.assertIsNone(cmd.quantity)
        self.assertFalse(cmd.requires_confirmation)

    def test_parse_low_stock_query(self):
        """Parse LOW_STOCK_QUERY command."""
        cmd = self.parser.parse("Show products that are running low")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.LOW_STOCK_QUERY)
        self.assertFalse(cmd.requires_confirmation)

    def test_parse_all_products_query(self):
        """Parse ALL_PRODUCTS_QUERY command."""
        cmd = self.parser.parse("Check stock for all products")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.ALL_PRODUCTS_QUERY)
        self.assertFalse(cmd.requires_confirmation)

    def test_parse_supplier_receipt(self):
        """Parse SUPPLIER_RECEIPT command."""
        cmd = self.parser.parse("Received 50 units of Coca Cola from supplier ABC Logistics")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.SUPPLIER_RECEIPT)
        self.assertEqual(cmd.quantity, 50)
        self.assertTrue(cmd.requires_confirmation)

    def test_invalid_negative_quantity_rejected(self):
        """Ensure negative or zero quantities raise validation errors on mutations."""
        with self.assertRaises(ValueError):
            InventoryVoiceCommand(
                command_type=InventoryVoiceCommandType.ADD_STOCK,
                quantity=-5,
                raw_transcript="Add -5 units",
            )

    def test_atomic_inventory_mutation_in_database(self):
        """Verify atomic stock update and delta tracking in database."""
        # 1. Update stock to 67 (+25)
        prev, updated = self.database.update_product_stock(self.product.id, 67)
        self.assertEqual(prev, 42)
        self.assertEqual(updated, 67)

        # 2. Adjust stock by -7
        prev_adj, new_adj = self.database.adjust_product_stock(self.product.id, -7)
        self.assertEqual(prev_adj, 67)
        self.assertEqual(new_adj, 60)

        # 3. Reject negative stock adjustment
        with self.assertRaises(ValueError):
            self.database.adjust_product_stock(self.product.id, -100)


if __name__ == "__main__":
    unittest.main()
