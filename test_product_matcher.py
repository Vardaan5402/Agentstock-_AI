"""Automated Unit Tests for Deterministic Product Matcher."""

import unittest
from models.inventory import Product
from core.product_matcher import ProductMatcher
from models.inventory_capture import ProductMatchStatus


class TestProductMatcher(unittest.TestCase):
    """Test deterministic product matching prioritization and ambiguity detection."""

    def setUp(self):
        self.catalog = [
            Product(
                id="prod_coke_500",
                business_id="biz_1",
                sku="COKE500",
                name="Coca Cola 500ml",
                current_stock=42,
                unit_cost=30.0,
                daily_demand=10.0,
                safety_stock=15,
            ),
            Product(
                id="prod_coke_1000",
                business_id="biz_1",
                sku="COKE1000",
                name="Coca Cola 1L",
                current_stock=20,
                unit_cost=55.0,
                daily_demand=5.0,
                safety_stock=8,
            ),
            Product(
                id="prod_pepsi_500",
                business_id="biz_1",
                sku="PEPSI500",
                name="Pepsi 500ml",
                current_stock=18,
                unit_cost=28.0,
                daily_demand=6.0,
                safety_stock=10,
            ),
            Product(
                id="prod_amul_taza",
                business_id="biz_1",
                sku="AMUL500",
                name="Amul Taza Fresh Milk 500ml",
                current_stock=50,
                unit_cost=27.0,
                daily_demand=25.0,
                safety_stock=20,
            ),
        ]
        self.matcher = ProductMatcher(self.catalog)

    def test_exact_sku_match(self):
        """Priority 1: Exact SKU match."""
        res = self.matcher.match("COKE500")
        self.assertEqual(res.status, ProductMatchStatus.EXACT_MATCH)
        self.assertIsNotNone(res.matched_product)
        self.assertEqual(res.matched_product.id, "prod_coke_500")

    def test_case_insensitive_sku_match(self):
        """Priority 1: Lowercase SKU match."""
        res = self.matcher.match("coke500")
        self.assertEqual(res.status, ProductMatchStatus.EXACT_MATCH)
        self.assertEqual(res.matched_product.sku, "COKE500")

    def test_exact_product_id_match(self):
        """Priority 2: Exact Product ID match."""
        res = self.matcher.match("prod_pepsi_500")
        self.assertEqual(res.status, ProductMatchStatus.EXACT_MATCH)
        self.assertEqual(res.matched_product.name, "Pepsi 500ml")

    def test_exact_name_match(self):
        """Priority 3: Exact Product Name match."""
        res = self.matcher.match("Coca Cola 500ml")
        self.assertEqual(res.status, ProductMatchStatus.EXACT_MATCH)
        self.assertEqual(res.matched_product.sku, "COKE500")

    def test_normalized_name_match(self):
        """Priority 4: Normalized punctuation/spacing match."""
        res = self.matcher.match("coca  cola  500ml!")
        self.assertIn(res.status, [ProductMatchStatus.EXACT_MATCH, ProductMatchStatus.NORMALIZED_MATCH])
        self.assertEqual(res.matched_product.sku, "COKE500")

    def test_fuzzy_clear_winner_match(self):
        """Priority 5: Token subset fuzzy match with clear winner."""
        res = self.matcher.match("Amul Taza Milk")
        self.assertIn(res.status, [ProductMatchStatus.FUZZY_MATCH, ProductMatchStatus.NORMALIZED_MATCH])
        self.assertIsNotNone(res.matched_product)
        self.assertEqual(res.matched_product.sku, "AMUL500")

    def test_ambiguous_matches(self):
        """Ambiguous query returns multiple candidates rather than picking randomly."""
        res = self.matcher.match("Coca Cola")
        # Both Coke 500ml and Coke 1L match with equal relevance
        self.assertEqual(res.status, ProductMatchStatus.AMBIGUOUS)
        self.assertIsNone(res.matched_product)
        self.assertGreaterEqual(len(res.candidates), 2)
        skus = {c.product.sku for c in res.candidates}
        self.assertIn("COKE500", skus)
        self.assertIn("COKE1000", skus)

    def test_product_not_found(self):
        """Unrecognized item returns NOT_FOUND."""
        res = self.matcher.match("Unknown Widget 999")
        self.assertEqual(res.status, ProductMatchStatus.NOT_FOUND)
        self.assertIsNone(res.matched_product)


if __name__ == "__main__":
    unittest.main()
