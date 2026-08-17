"""Test Suite for Multilingual Voice Inventory Assistant Parsing."""
import unittest
from core.voice_inventory import VoiceInventoryParser
from models.inventory_capture import InventoryVoiceCommandType


class TestMultilingualVoice(unittest.TestCase):
    """Test natural language speech parsing across English, Hindi patterns, and queries."""

    def setUp(self):
        self.parser = VoiceInventoryParser()

    def test_english_add_stock_command(self):
        cmd = self.parser.parse("Add 25 packets of basmati rice")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.ADD_STOCK)
        self.assertEqual(cmd.quantity, 25)
        self.assertIn("basmati rice", cmd.product_identifier.lower())

    def test_hindi_transliterated_add_stock_command(self):
        cmd = self.parser.parse("25 packet rice add karo")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.ADD_STOCK)
        self.assertEqual(cmd.quantity, 25)
        self.assertIn("rice", cmd.product_identifier.lower())

    def test_english_remove_stock_command(self):
        cmd = self.parser.parse("Remove 10 units of whole milk")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.REMOVE_STOCK)
        self.assertEqual(cmd.quantity, 10)
        self.assertIn("whole milk", cmd.product_identifier.lower())

    def test_low_stock_query_command(self):
        cmd = self.parser.parse("Show all products running low on stock")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.LOW_STOCK_QUERY)

    def test_all_products_query_command(self):
        cmd = self.parser.parse("List all products in inventory")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.ALL_PRODUCTS_QUERY)

    def test_written_word_number_conversion(self):
        cmd = self.parser.parse("Add fifty units of olive oil")
        self.assertEqual(cmd.command_type, InventoryVoiceCommandType.ADD_STOCK)
        self.assertEqual(cmd.quantity, 50)
        self.assertIn("olive oil", cmd.product_identifier.lower())


if __name__ == "__main__":
    unittest.main()
