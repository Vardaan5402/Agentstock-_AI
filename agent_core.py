import os
import json
from datetime import datetime
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Initialize client using environment credentials
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

class InventoryDecision(BaseModel):
    item_name: str = Field(description="Name of the inventory item")
    current_stock_level: int = Field(description="Current units remaining in stock")
    burn_rate_per_day: float = Field(description="Estimated daily consumption rate")
    days_until_stockout: float = Field(description="Calculated runway before stock exhaustion")
    reorder_recommended: bool = Field(description="True if stock is critically low")
    suggested_purchase_quantity: int = Field(description="Optimal reorder quantity to achieve safety stock")
    supplier_email_draft: str = Field(description="Professional, ready-to-dispatch purchase order email text")

def analyze_single_sku(sku: str, item_name: str, stock: int, burn: float, supplier: str, currency: str) -> dict:
    """
    Executes a deep autonomous evaluation loop for an individual SKU using Gemini 2.5 Flash 
    with enforced Pydantic schemas.
    """
    days_left = round(stock / burn, 1) if burn > 0 else 99.9
    reorder_needed = days_left <= 3.5
    suggested_qty = int(burn * 10) if reorder_needed else 0

    prompt = f"""
    You are the Chief Supply Chain Officer of AgentStock AI, an autonomous enterprise agent.
    Evaluate the following stock parameters:
    - SKU ID: {sku}
    - Item: {item_name}
    - Current Inventory: {stock} units
    - Daily Consumption Rate: {burn} units/day
    - Projected Runway: {days_left} days
    - Designated Supplier: {supplier}
    - Operating Currency: {currency}

    Determine if an emergency restocking sequence is mandatory. If reorder_recommended is true, draft a formal, professional purchase order email to the supplier specifying the exact quantity ({suggested_qty} units).
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=InventoryDecision,
                temperature=0.1,
            ),
        )
        
        result = json.loads(response.text)
        result["timestamp"] = datetime.utcnow().isoformat()
        result["sku"] = sku
        return result
    except Exception as e:
        return {
            "sku": sku,
            "item_name": item_name,
            "days_until_stockout": days_left,
            "reorder_recommended": reorder_needed,
            "suggested_purchase_quantity": suggested_qty,
            "supplier_email_draft": f"Error executing autonomous agent loop: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

def process_invoice_document(file_bytes: bytes, mime_type: str) -> str:
    """
    Multimodal ingestion pipeline using Gemini vision capabilities to extract line items,
    quantities, and supplier pricing directly from unstructured invoices or PDFs.
    """
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            types.Part.from_bytes(
                data=file_bytes,
                mime_type=mime_type,
            ),
            (
                "You are an automated logistics parser. Extract all line items, SKU references, "
                "quantities received, and unit costs from this document. Format the output "
                "as a clean Markdown table with clear operational insights for inventory reconciliation."
            )
        ],
    )
    return response.text