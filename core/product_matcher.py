"""Deterministic Product Matcher for Voice and Vision Inventory Capture."""

import re
import difflib
from typing import List, Optional
from models.inventory import Product
from models.inventory_capture import (
    ProductMatchCandidate,
    ProductMatchResult,
    ProductMatchStatus,
)


def _normalize_text(text: str) -> str:
    """Normalize string for robust product name comparison."""
    if not text:
        return ""
    # Lowercase, remove special characters and punctuation
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    # Collapse multiple whitespaces
    return re.sub(r"\s+", " ", cleaned).strip()


def _tokenize_text(text: str) -> set[str]:
    """Tokenize normalized text into unique words, stripping minor noise tokens."""
    norm = _normalize_text(text)
    tokens = set(norm.split())
    # Noise words that shouldn't distort matching
    noise = {"a", "an", "the", "units", "unit", "pieces", "pcs", "of", "in", "for", "pack", "box"}
    return tokens - noise


class ProductMatcher:
    """Matches product names, SKUs, or barcodes against a catalog with strict deterministic priority."""

    def __init__(self, catalog: List[Product]):
        self.catalog = list(catalog)

    def match(self, query: str, top_k: int = 5) -> ProductMatchResult:
        """Find the best product match in the catalog using prioritized matching rules."""
        raw_query = (query or "").strip()
        if not raw_query:
            return ProductMatchResult(status=ProductMatchStatus.NOT_FOUND, candidates=[], query=raw_query)

        norm_query = _normalize_text(raw_query)
        query_tokens = _tokenize_text(raw_query)

        # 1. Exact SKU Match (Case-insensitive)
        for prod in self.catalog:
            if prod.sku.strip().lower() == raw_query.lower() or prod.sku.strip().lower() == norm_query:
                candidate = ProductMatchCandidate(product=prod, match_score=1.0, match_type="EXACT_SKU")
                return ProductMatchResult(
                    status=ProductMatchStatus.EXACT_MATCH,
                    matched_product=prod,
                    candidates=[candidate],
                    query=raw_query,
                )

        # 2. Exact Product ID Match
        for prod in self.catalog:
            if prod.id.strip().lower() == raw_query.lower():
                candidate = ProductMatchCandidate(product=prod, match_score=1.0, match_type="EXACT_ID")
                return ProductMatchResult(
                    status=ProductMatchStatus.EXACT_MATCH,
                    matched_product=prod,
                    candidates=[candidate],
                    query=raw_query,
                )

        # 3. Exact Product Name Match (Case-insensitive)
        for prod in self.catalog:
            if prod.name.strip().lower() == raw_query.lower():
                candidate = ProductMatchCandidate(product=prod, match_score=0.99, match_type="EXACT_NAME")
                return ProductMatchResult(
                    status=ProductMatchStatus.EXACT_MATCH,
                    matched_product=prod,
                    candidates=[candidate],
                    query=raw_query,
                )

        # 4. Normalized Product Name Match
        for prod in self.catalog:
            if _normalize_text(prod.name) == norm_query:
                candidate = ProductMatchCandidate(product=prod, match_score=0.95, match_type="NORMALIZED_NAME")
                return ProductMatchResult(
                    status=ProductMatchStatus.NORMALIZED_MATCH,
                    matched_product=prod,
                    candidates=[candidate],
                    query=raw_query,
                )

        # 5. Token Subset & Fuzzy Matching
        scored_candidates: List[ProductMatchCandidate] = []
        for prod in self.catalog:
            prod_norm = _normalize_text(prod.name)
            prod_tokens = _tokenize_text(prod.name)

            # Token overlap score
            if query_tokens and prod_tokens:
                intersection = query_tokens.intersection(prod_tokens)
                token_jaccard = len(intersection) / len(query_tokens.union(prod_tokens))
                # Subset bonus if all query tokens are present in product
                if query_tokens.issubset(prod_tokens):
                    token_jaccard = max(token_jaccard, 0.85)
            else:
                token_jaccard = 0.0

            # String similarity (SequenceMatcher)
            seq_ratio = difflib.SequenceMatcher(None, norm_query, prod_norm).ratio()
            sku_seq_ratio = difflib.SequenceMatcher(None, norm_query, _normalize_text(prod.sku)).ratio()

            best_score = max(token_jaccard, seq_ratio, sku_seq_ratio)

            if best_score >= 0.45:
                match_type = "SUBSET_TOKENS" if token_jaccard >= 0.8 else "FUZZY_RATIO"
                scored_candidates.append(
                    ProductMatchCandidate(product=prod, match_score=round(best_score, 3), match_type=match_type)
                )

        scored_candidates.sort(key=lambda c: c.match_score, reverse=True)
        top_candidates = scored_candidates[:top_k]

        if not top_candidates:
            return ProductMatchResult(status=ProductMatchStatus.NOT_FOUND, candidates=[], query=raw_query)

        # Check if single clear winner (score >= 0.75 and at least 0.15 higher than 2nd candidate)
        if len(top_candidates) == 1 and top_candidates[0].match_score >= 0.65:
            return ProductMatchResult(
                status=ProductMatchStatus.FUZZY_MATCH,
                matched_product=top_candidates[0].product,
                candidates=top_candidates,
                query=raw_query,
            )

        if len(top_candidates) > 1:
            first = top_candidates[0]
            second = top_candidates[1]
            if first.match_score >= 0.80 and (first.match_score - second.match_score) >= 0.20:
                return ProductMatchResult(
                    status=ProductMatchStatus.FUZZY_MATCH,
                    matched_product=first.product,
                    candidates=top_candidates,
                    query=raw_query,
                )
            # Ambiguous: multiple close candidates
            return ProductMatchResult(
                status=ProductMatchStatus.AMBIGUOUS,
                matched_product=None,
                candidates=top_candidates,
                query=raw_query,
            )

        if top_candidates[0].match_score >= 0.60:
            return ProductMatchResult(
                status=ProductMatchStatus.FUZZY_MATCH,
                matched_product=top_candidates[0].product,
                candidates=top_candidates,
                query=raw_query,
            )

        return ProductMatchResult(status=ProductMatchStatus.NOT_FOUND, candidates=top_candidates, query=raw_query)
