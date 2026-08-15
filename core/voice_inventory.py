"""Voice Inventory Assistant & Natural Language Command Parser."""

import re
import json
from typing import Optional, List, Tuple
from core.config import get_gemini_api_key
from models.inventory import Product
from models.inventory_capture import (
    InventoryVoiceCommand,
    InventoryVoiceCommandType,
    ProductMatchResult,
    ProductMatchStatus,
)
from core.product_matcher import ProductMatcher


_WORD_TO_NUMBER = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "twenty five": 25, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "one hundred": 100,
}


def _replace_number_words(text: str) -> str:
    """Normalize written English numbers into Arabic digits."""
    s = text.lower()
    for word, num in sorted(_WORD_TO_NUMBER.items(), key=lambda x: len(x[0]), reverse=True):
        s = re.sub(rf"\b{re.escape(word)}\b", str(num), s)
    return s


class VoiceInventoryParser:
    """Parses natural language speech transcripts into structured, fact-bounded InventoryVoiceCommands."""

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.api_key = gemini_api_key or get_gemini_api_key()

    def parse(self, transcript: str) -> InventoryVoiceCommand:
        """Parse voice transcript using fast deterministic rules first, with Gemini structured fallback."""
        raw_text = (transcript or "").strip()
        if not raw_text:
            return InventoryVoiceCommand(
                command_type=InventoryVoiceCommandType.UNKNOWN,
                raw_transcript=raw_text,
                explanation="No speech or transcript was provided.",
                confidence=0.0,
            )

        norm_text = _replace_number_words(raw_text)

        # 1. Deterministic Rule Matching
        rule_result = self._try_rule_based_parse(norm_text, raw_text)
        if rule_result is not None:
            return rule_result

        # 2. Gemini Structured Fallback (if API key available)
        if self.api_key:
            try:
                gemini_result = self._parse_with_gemini(raw_text)
                if gemini_result is not None:
                    return gemini_result
            except Exception:
                pass

        # 3. Default fallback
        return InventoryVoiceCommand(
            command_type=InventoryVoiceCommandType.UNKNOWN,
            raw_transcript=raw_text,
            explanation=f"Could not identify a recognized inventory action from: '{raw_text}'",
            confidence=0.3,
        )

    def _try_rule_based_parse(self, text: str, raw_text: str) -> Optional[InventoryVoiceCommand]:
        """Fast regex patterns for common inventory phrasing."""
        lower = text.lower()

        # Check for LOW_STOCK_QUERY
        if re.search(r"\b(show|check|list|find|what)\b.*\b(running low|low stock|out of stock|stockout|critical)\b", lower):
            return InventoryVoiceCommand(
                command_type=InventoryVoiceCommandType.LOW_STOCK_QUERY,
                raw_transcript=raw_text,
                explanation="Query for items below safety stock / reorder threshold.",
                confidence=0.98,
            )

        # Check for ALL_PRODUCTS_QUERY
        if re.search(r"\b(show|check|list|get)\b.*\b(all products|all stock|entire inventory|all items)\b", lower):
            return InventoryVoiceCommand(
                command_type=InventoryVoiceCommandType.ALL_PRODUCTS_QUERY,
                raw_transcript=raw_text,
                explanation="Query stock levels across all catalog items.",
                confidence=0.98,
            )

        # Check for ADD_STOCK
        # e.g., "Add 25 units of Coca Cola 500ml", "Add 10 Nike shoes"
        m_add = re.search(r"\badd\s+(\d+)\s*(?:units\s+of|units|pcs\s+of|pcs|boxes\s+of|boxes|cases\s+of)?\s*(.+)", lower)
        if m_add:
            qty = int(m_add.group(1))
            prod_str = m_add.group(2).strip(" .?!")
            return InventoryVoiceCommand(
                command_type=InventoryVoiceCommandType.ADD_STOCK,
                quantity=qty,
                product_identifier=prod_str,
                product_name=prod_str,
                raw_transcript=raw_text,
                explanation=f"Add {qty} units to inventory for '{prod_str}'.",
                confidence=0.95,
            )

        # Check for REMOVE_STOCK
        # e.g., "Remove 5 units of SKU ABC123", "Deduct 10 units of Sprite"
        m_rem = re.search(r"\b(?:remove|deduct|subtract|discard)\s+(\d+)\s*(?:units\s+of|units|pcs\s+of|pcs)?\s*(.+)", lower)
        if m_rem:
            qty = int(m_rem.group(1))
            prod_str = m_rem.group(2).strip(" .?!")
            return InventoryVoiceCommand(
                command_type=InventoryVoiceCommandType.REMOVE_STOCK,
                quantity=qty,
                product_identifier=prod_str,
                product_name=prod_str,
                raw_transcript=raw_text,
                explanation=f"Remove {qty} units from inventory for '{prod_str}'.",
                confidence=0.95,
            )

        # Check for SET_STOCK
        # e.g., "Set the stock of product XYZ to 100", "Set Coca Cola to 50"
        m_set = re.search(r"\bset\s+(?:the\s+)?(?:stock\s+of\s+|inventory\s+of\s+)?(.+?)\s+(?:to|equal\s+to)\s+(\d+)", lower)
        if m_set:
            prod_str = m_set.group(1).strip(" .?!")
            qty = int(m_set.group(2))
            return InventoryVoiceCommand(
                command_type=InventoryVoiceCommandType.SET_STOCK,
                quantity=qty,
                product_identifier=prod_str,
                product_name=prod_str,
                raw_transcript=raw_text,
                explanation=f"Set stock count for '{prod_str}' to {qty} units.",
                confidence=0.95,
            )

        # Check for SUPPLIER_RECEIPT
        # e.g., "Received 50 units from supplier ABC", "Received 50 units of Milk from supplier ABC"
        m_rec = re.search(r"\b(?:received|got|accepted)\s+(\d+)\s*(?:units\s+of|units)?\s*(.+?)(?:\s+from\s+(?:supplier\s+)?(.+))?$", lower)
        if m_rec:
            qty = int(m_rec.group(1))
            prod_str = m_rec.group(2).strip(" .?!")
            supplier_str = m_rec.group(3).strip(" .?!") if m_rec.group(3) else None
            return InventoryVoiceCommand(
                command_type=InventoryVoiceCommandType.SUPPLIER_RECEIPT,
                quantity=qty,
                product_identifier=prod_str,
                product_name=prod_str,
                supplier_identifier=supplier_str,
                raw_transcript=raw_text,
                explanation=f"Record receipt of {qty} units of '{prod_str}'" + (f" from supplier '{supplier_str}'." if supplier_str else "."),
                confidence=0.92,
            )

        # Check for QUERY_STOCK
        # e.g., "What's the current stock of SKU ABC123?", "How many units of Coca Cola are in stock?"
        m_qry = re.search(r"\b(?:how\s+many|what\s+is\s+the|what's\s+the|check|show|get|find)\s+(?:units\s+of\s+)?(?:current\s+)?(?:stock\s+of\s+|stock\s+for\s+|inventory\s+of\s+)?(.+)", lower)
        if m_qry:
            prod_str = m_qry.group(1).strip(" .?!")
            # Clean trailing words like "are in stock", "in stock"
            prod_str = re.sub(r"\s+(?:are\s+in\s+stock|in\s+stock|available)$", "", prod_str).strip()
            if prod_str:
                return InventoryVoiceCommand(
                    command_type=InventoryVoiceCommandType.QUERY_STOCK,
                    product_identifier=prod_str,
                    product_name=prod_str,
                    raw_transcript=raw_text,
                    explanation=f"Query current on-hand stock for '{prod_str}'.",
                    confidence=0.92,
                )

        return None

    def _parse_with_gemini(self, transcript: str) -> Optional[InventoryVoiceCommand]:
        """Use Gemini model to parse complex conversational phrasing into strict structured command schema."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        prompt = (
            "You are an AI Voice Inventory Parser. Convert the following spoken user transcript "
            "into a strict JSON object conforming to the schema.\n\n"
            "Rules:\n"
            "1. Allowed command_type values: QUERY_STOCK, ADD_STOCK, REMOVE_STOCK, SET_STOCK, LOW_STOCK_QUERY, ALL_PRODUCTS_QUERY, SUPPLIER_RECEIPT, UNKNOWN\n"
            "2. Extract clean product_name, sku (if specified), quantity (integer, null for queries), supplier_identifier (if specified).\n"
            "3. If quantity is specified, ensure it is a positive integer (> 0) except for SET_STOCK which can be >= 0.\n"
            "4. Do NOT execute or invent facts. Return only the structured interpretation.\n\n"
            f"Transcript: \"{transcript}\""
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=InventoryVoiceCommand,
                temperature=0.0,
            ),
        )
        if response.text:
            data = json.loads(response.text)
            data["raw_transcript"] = transcript
            return InventoryVoiceCommand.model_validate(data)
        return None
