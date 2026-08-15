"""Domain models for Voice and Vision Inventory Capture & Reconciliation."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
from models.inventory import Product


class InventoryVoiceCommandType(str, Enum):
    """Allowed intent types for voice inventory commands."""

    QUERY_STOCK = "QUERY_STOCK"
    ADD_STOCK = "ADD_STOCK"
    REMOVE_STOCK = "REMOVE_STOCK"
    SET_STOCK = "SET_STOCK"
    LOW_STOCK_QUERY = "LOW_STOCK_QUERY"
    ALL_PRODUCTS_QUERY = "ALL_PRODUCTS_QUERY"
    SUPPLIER_RECEIPT = "SUPPLIER_RECEIPT"
    UNKNOWN = "UNKNOWN"


class InventoryVoiceCommand(BaseModel):
    """Structured, fact-bounded representation of a natural language inventory instruction."""

    command_type: InventoryVoiceCommandType
    product_identifier: Optional[str] = None
    product_name: Optional[str] = None
    sku: Optional[str] = None
    quantity: Optional[int] = None
    supplier_identifier: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    raw_transcript: str = Field(min_length=1)
    explanation: str = Field(default="")
    requires_confirmation: bool = False

    @model_validator(mode="after")
    def validate_command_integrity(self) -> "InventoryVoiceCommand":
        # Mutations must have a valid quantity and require user confirmation
        if self.command_type in {
            InventoryVoiceCommandType.ADD_STOCK,
            InventoryVoiceCommandType.REMOVE_STOCK,
            InventoryVoiceCommandType.SUPPLIER_RECEIPT,
        }:
            self.requires_confirmation = True
            if self.quantity is not None and self.quantity <= 0:
                raise ValueError(f"Quantity for {self.command_type.value} must be greater than 0")
        elif self.command_type == InventoryVoiceCommandType.SET_STOCK:
            self.requires_confirmation = True
            if self.quantity is not None and self.quantity < 0:
                raise ValueError("Quantity for SET_STOCK cannot be negative")
        else:
            # Queries do not require destructive confirmation
            self.requires_confirmation = False
        return self


class ProductMatchStatus(str, Enum):
    """Status of matching an identifier against the product database."""

    EXACT_MATCH = "EXACT_MATCH"
    NORMALIZED_MATCH = "NORMALIZED_MATCH"
    FUZZY_MATCH = "FUZZY_MATCH"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


class ProductMatchCandidate(BaseModel):
    """A matched candidate product with similarity score."""

    product: Product
    match_score: float = Field(ge=0.0, le=1.0)
    match_type: str


class ProductMatchResult(BaseModel):
    """Deterministic result of matching a voice/vision query against inventory."""

    status: ProductMatchStatus
    matched_product: Optional[Product] = None
    candidates: List[ProductMatchCandidate] = Field(default_factory=list)
    query: str


class InventoryVisionItem(BaseModel):
    """An individual product or shelf item extracted from visual inspection."""

    product_name: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    observed_quantity: Optional[int] = Field(default=None, ge=0)
    unit: Optional[str] = "units"
    package_size: Optional[str] = None
    location: Optional[str] = None
    supplier: Optional[str] = None
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    evidence: str = Field(default="")


class InventoryVisionResult(BaseModel):
    """Strict structured extraction result from Gemini Vision or Barcode decoder."""

    items: List[InventoryVisionItem] = Field(default_factory=list)
    image_hash: str = Field(min_length=1)
    model: str = "gemini-2.5-flash"
    warnings: List[str] = Field(default_factory=list)
    extraction_confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class ReconciliationItemStatus(str, Enum):
    """Comparison status between observed vision inventory and system database."""

    MATCH = "MATCH"
    SURPLUS = "SURPLUS"
    DEFICIT = "DEFICIT"
    UNQUANTIFIABLE = "UNQUANTIFIABLE"
    UNREGISTERED = "UNREGISTERED"


class InventoryReconciliationItem(BaseModel):
    """Discrepancy and alignment row between visual scan and database record."""

    item_id: str
    product: Optional[Product] = None
    detected_name: str
    detected_sku: Optional[str] = None
    detected_barcode: Optional[str] = None
    observed_quantity: Optional[int] = None
    system_stock: Optional[int] = None
    discrepancy: Optional[int] = None
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    evidence: str = ""
    status: ReconciliationItemStatus
    selected_for_reconciliation: bool = True


class InventoryReconciliationReport(BaseModel):
    """Comprehensive visual reconciliation report for a scanned image."""

    reconciliation_id: str
    image_hash: str
    items: List[InventoryReconciliationItem] = Field(default_factory=list)
    total_detected: int = 0
    total_discrepancies: int = 0
    total_matched: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
