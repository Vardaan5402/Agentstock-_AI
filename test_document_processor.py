"""Test Suite for Document Processor, MIME validation, and CSV Parsing."""
import os
import unittest
from core.document_processor import DocumentProcessor


class TestDocumentProcessor(unittest.TestCase):
    """Test file validation, CSV parsing, and malicious script rejection."""

    def setUp(self):
        self.processor = DocumentProcessor(upload_dir="test_uploads")

    def tearDown(self):
        if os.path.exists("test_uploads"):
            import shutil
            try:
                shutil.rmtree("test_uploads")
            except Exception:
                pass

    def test_csv_inventory_extraction(self):
        csv_data = b"name,sku,stock,cost\nOrganic Milk 1L,MILK-01,150,55.0\nBasmati Rice 5kg,RICE-05,80,320.0\n"
        res = self.processor.extract_inventory_data("inventory.csv", csv_data)

        self.assertEqual(res["status"], "PROCESSED")
        self.assertEqual(res["extracted_count"], 2)
        items = res["items"]
        self.assertEqual(items[0]["sku"], "MILK-01")
        self.assertEqual(items[0]["current_stock"], 150)
        self.assertEqual(items[0]["unit_cost"], 55.0)

    def test_file_validation_valid_and_invalid_extensions(self):
        # Valid PDF
        valid, _ = self.processor.validate_file("invoice.pdf", b"%PDF-1.4 mock content")
        self.assertTrue(valid)

        # Invalid .exe
        valid_exe, msg_exe = self.processor.validate_file("malicious.exe", b"binary content")
        self.assertFalse(valid_exe)
        self.assertIn("not supported", msg_exe.lower())

    def test_malicious_script_rejection(self):
        # Embedded web script inside csv
        hacked_csv = b"<script>alert('xss')</script>,SKU-01,10,5.0"
        valid, msg = self.processor.validate_file("hacked.csv", hacked_csv)
        self.assertFalse(valid)
        self.assertIn("rejected", msg.lower())

    def test_size_limit_enforcement(self):
        # 11 MB payload
        large_bytes = b"0" * (11 * 1024 * 1024)
        valid, msg = self.processor.validate_file("large.pdf", large_bytes)
        self.assertFalse(valid)
        self.assertIn("exceeds 10mb limit", msg.lower())


if __name__ == "__main__":
    unittest.main()
