"""Gemini Vision Inventory Extraction Adapter."""

import os
import json
import hashlib
from typing import Optional, List
from core.config import get_gemini_api_key
from models.inventory_capture import (
    InventoryVisionItem,
    InventoryVisionResult,
)


class GeminiInventoryVisionAnalyzer:
    """Extracts structured product, SKU, barcode, and visible stock counts from images via Gemini Vision."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or get_gemini_api_key()
        self.model = model

    def analyze_image(
        self, image_bytes: bytes, mime_type: str = "image/jpeg"
    ) -> InventoryVisionResult:
        """Analyze an image of shelves, cartons, or product labels into structured inventory items."""
        image_hash = hashlib.sha256(image_bytes).hexdigest()

        if not self.api_key:
            # Safe offline fallback for local tests or environments without API keys
            return InventoryVisionResult(
                items=[],
                image_hash=image_hash,
                model=self.model,
                warnings=["Gemini API key is not configured. Vision extraction offline."],
                extraction_confidence=0.0,
            )

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        prompt = (
            "You are an expert industrial inventory vision analyzer. Analyze the provided image of "
            "product shelves, cartons, retail racks, delivery boxes, or inventory barcodes/labels.\n\n"
            "CRITICAL ACCURACY RULES:\n"
            "1. DO NOT INVENT OR HALLUCINATE QUANTITIES. If an exact count cannot be clearly verified "
            "(e.g., items stacked behind each other, partially obscured boxes, or distant shelves), "
            "set `observed_quantity: null` and document this in the `evidence` field.\n"
            "2. Extract legible product names, SKUs, and barcodes exactly as printed on labels or packaging.\n"
            "3. If multiple distinct products are visible in the image, return a separate item entry for each.\n"
            "4. Provide visual evidence text explaining how the product and count were identified.\n"
            "5. Never convert visual uncertainty into a guessed number.\n"
        )

        try:
            image_part = types.Part.from_bytes(
                data=image_bytes,
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
