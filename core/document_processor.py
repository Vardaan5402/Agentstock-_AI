"""Business Inventory Document Processor (PDF, CSV, XLSX, Invoices)."""
import os
import io
import re
import csv
import json
import secrets
from typing import Optional, List, Dict, Any, Tuple
from core.config import get_gemini_api_key
from models.security import UploadedDocument
from core.security import ContentModerationGuard


class DocumentProcessor:
    """Validates, sanitizes, and extracts inventory lines from uploaded business documents."""

    ALLOWED_MIME_TYPES = {
        "application/pdf": ".pdf",
        "text/csv": ".csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }

    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)
        self.api_key = get_gemini_api_key()

    def validate_file(self, filename: str, file_bytes: bytes, mime_type: Optional[str] = None) -> Tuple[bool, str]:
        """Validate file size, extension, and content safety."""
        if not file_bytes:
            return False, "Uploaded file is empty."

        if len(file_bytes) > self.MAX_FILE_SIZE_BYTES:
            return False, f"File size exceeds 10MB limit ({len(file_bytes)/(1024*1024):.1f}MB)."

        # Extension check
        ext = os.path.splitext(filename.lower())[1]
        valid_extensions = {".pdf", ".csv", ".xlsx", ".png", ".jpg", ".jpeg", ".webp"}
        if ext not in valid_extensions:
            return False, f"File extension '{ext}' is not supported. Please upload PDF, CSV, XLSX, PNG, or JPG."

        # Content check for dangerous scripts
        first_kb = file_bytes[:1024].decode("utf-8", errors="ignore").lower()
        if "<script" in first_kb or "<?php" in first_kb or "eval(" in first_kb or "<html" in first_kb:
            return False, "File rejected: executable code or web scripts are prohibited."

        return True, "File valid"

    def save_file_securely(self, user_id: str, filename: str, file_bytes: bytes) -> str:
        """Save file in tenant-isolated directory with randomized name."""
        user_dir = os.path.join(self.upload_dir, f"user_{user_id}")
        os.makedirs(user_dir, exist_ok=True)

        ext = os.path.splitext(filename.lower())[1]
        safe_name = f"doc_{secrets.token_hex(8)}{ext}"
        full_path = os.path.join(user_dir, safe_name)

        with open(full_path, "wb") as f:
            f.write(file_bytes)

        return full_path

    def extract_inventory_data(self, filename: str, file_bytes: bytes) -> Dict[str, Any]:
        """Extract structured inventory items from CSV, text, or Gemini Document AI."""
        ext = os.path.splitext(filename.lower())[1]

        if ext == ".csv":
            return self._parse_csv(file_bytes)

        # PDF / Image Document Extraction via Gemini or Heuristic
        if self.api_key:
            return self._extract_with_gemini(filename, file_bytes)

        # Standalone heuristic fallback
        return {
            "items": [],
            "summary": "Document received and safely stored. Connect GEMINI_API_KEY for automatic line-item parsing.",
            "status": "PROCESSED",
            "extracted_count": 0,
        }

    def _parse_csv(self, file_bytes: bytes) -> Dict[str, Any]:
        """Parse structured CSV inventory rows."""
        try:
            content = file_bytes.decode("utf-8", errors="ignore")
            reader = csv.DictReader(io.StringIO(content))
            items = []
            for row in reader:
                # Find common column names
                name = row.get("name") or row.get("product_name") or row.get("item") or row.get("Product")
                sku = row.get("sku") or row.get("SKU") or row.get("code")
                stock_str = row.get("stock") or row.get("current_stock") or row.get("quantity") or row.get("qty") or "0"
                cost_str = row.get("cost") or row.get("unit_cost") or row.get("price") or "0.0"

                if name or sku:
                    try:
                        stock = int(float(stock_str))
                    except ValueError:
                        stock = 0
                    try:
                        cost = float(cost_str.replace("₹", "").replace("$", "").replace(",", ""))
                    except ValueError:
                        cost = 0.0

                    items.append({
                        "product_name": str(name or sku).strip(),
                        "sku": str(sku or name).strip(),
                        "current_stock": stock,
                        "unit_cost": cost,
                    })

            return {
                "items": items,
                "summary": f"Extracted {len(items)} product rows from CSV.",
                "status": "PROCESSED",
                "extracted_count": len(items),
            }
        except Exception as e:
            return {
                "items": [],
                "summary": f"CSV parse error: {str(e)}",
                "status": "FAILED",
                "extracted_count": 0,
            }

    def _extract_with_gemini(self, filename: str, file_bytes: bytes) -> Dict[str, Any]:
        """Extract invoice and receipt items using Gemini."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        ext = os.path.splitext(filename.lower())[1]
        mime = "application/pdf" if ext == ".pdf" else "image/jpeg"

        prompt = (
            "You are an expert commercial document reader. Extract inventory line items from this "
            "business document (invoice, purchase order, packing slip, or stock report).\n\n"
            "Return JSON matching:\n"
            "{\n"
            "  \"items\": [\n"
            "    {\"product_name\": str, \"sku\": str, \"quantity\": int, \"unit_cost\": float}\n"
            "  ],\n"
            "  \"summary\": str,\n"
            "  \"supplier_name\": str (optional)\n"
            "}\n"
            "Rules:\n"
            "1. Only include verifiable product lines.\n"
            "2. Do not invent or guess numbers.\n"
        )

        try:
            part = types.Part.from_bytes(data=file_bytes, mime_type=mime)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt, part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            if resp.text:
                data = json.loads(resp.text)
                data["status"] = "PROCESSED"
                data["extracted_count"] = len(data.get("items", []))
                return data
        except Exception as err:
            return {
                "items": [],
                "summary": f"Document extraction error: {str(err)}",
                "status": "FAILED",
                "extracted_count": 0,
            }

        return {
            "items": [],
            "summary": "No inventory line items found.",
            "status": "PROCESSED",
            "extracted_count": 0,
        }
