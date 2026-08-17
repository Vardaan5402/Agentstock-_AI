"""Gemini Vision Inventory Extraction with Privacy Person Filter & Confidence Scoring."""
import os
import json
import hashlib
from typing import Optional, List, Tuple
from core.config import get_gemini_api_key
from core.security import PrivacyPersonFilter
from models.inventory_capture import (
    InventoryVisionItem,
    InventoryVisionResult,
)


class GeminiInventoryVisionAnalyzer:
    """Extracts structured product, SKU, barcode, and visible stock counts with strict privacy filtering."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or get_gemini_api_key()
        self.model = model

    def analyze_image(
        self, image_bytes: bytes, mime_type: str = "image/jpeg"
    ) -> InventoryVisionResult:
        """Analyze an image of shelves, cartons, or product labels with privacy person detection."""
        image_hash = hashlib.sha256(image_bytes).hexdigest()

        # Step 1: Privacy Person Filter
        has_person, privacy_msg = PrivacyPersonFilter.inspect_image_for_persons(image_bytes)
        if has_person:
            return InventoryVisionResult(
                items=[],
                image_hash=image_hash,
                model=self.model,
                warnings=["PRIVACY_FILTER: A person was detected in the frame. Please point the camera only at inventory items."],
                extraction_confidence=0.0,
            )

        sanitized_bytes = PrivacyPersonFilter.sanitize_person_frame(image_bytes)

        # Step 2: Offline fallback if no API key
        if not self.api_key:
            return InventoryVisionResult(
                items=[],
                image_hash=image_hash,
                model=self.model,
                warnings=["Gemini API key is not configured. Vision extraction offline."],
                extraction_confidence=0.0,
            )

        # Step 3: Multimodal Extraction via Gemini
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        prompt = (
            "You are an industrial inventory vision analyzer for retail stores and warehouses.\n"
            "Analyze the provided image of product shelves, cartons, boxes, or barcodes.\n\n"
            "PRIVACY RULE:\n"
            "If any human face or person is clearly prominent in the image, return an empty items list and "
            "set warnings to ['Person detected in frame. Please point only at inventory.'].\n\n"
            "COUNTING & ACCURACY RULES:\n"
            "1. DO NOT GUESS OR INVENT COUNTS. If items are stacked deep or obscured, set observed_quantity: null "
            "and explain in the evidence field.\n"
            "2. Extract legible product names, SKUs, and barcodes as printed.\n"
            "3. Return confidence score (0.0 to 1.0) for each detected product.\n"
            "4. Provide short visual evidence (e.g. 'Counted 4 rows of 3 bottles on shelf level 1')."
        )

        try:
            image_part = types.Part.from_bytes(
                data=sanitized_bytes,
                mime_type=mime_type,
            )

            response = client.models.generate_content(
                model=self.model,
                contents=[prompt, image_part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=InventoryVisionResult,
                    temperature=0.0,
                ),
            )

            if response.text:
                data = json.loads(response.text)
                data["image_hash"] = image_hash
                data["model"] = self.model
                return InventoryVisionResult.model_validate(data)

            return InventoryVisionResult(
                items=[],
                image_hash=image_hash,
                model=self.model,
                warnings=["Model returned empty response."],
                extraction_confidence=0.0,
            )

        except Exception as error:
            return InventoryVisionResult(
                items=[],
                image_hash=image_hash,
                model=self.model,
                warnings=[f"Vision extraction failed: {str(error)}"],
                extraction_confidence=0.0,
            )
