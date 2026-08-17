"""Supplier domain models with commercial terms and delivery contact fields."""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class Supplier(BaseModel):
    """A supplier available to a business with full commercial contact attributes."""

    id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    user_id: Optional[str] = None
    name: str = Field(min_length=1)
    company_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    delivery_person_name: Optional[str] = None
    delivery_person_phone: Optional[str] = None
    gst_id: Optional[str] = None
    payment_terms: Optional[str] = "Net 30"
    supplier_category: Optional[str] = "General"
    notes: Optional[str] = None
    lead_time_days: float = Field(default=1.0, ge=0)
    reliability_score: float = Field(default=0.5, ge=0, le=1)
    is_archived: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SupplierProduct(BaseModel):
    """The commercial terms for a supplier/product pairing."""

    supplier_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    unit_price: float = Field(ge=0)
    minimum_order_quantity: int = Field(default=1, gt=0)
