"""Supplier domain models."""

from pydantic import BaseModel, Field


class Supplier(BaseModel):
    """A supplier available to a business."""

    id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    phone: str | None = None
    email: str | None = None
    lead_time_days: float = Field(ge=0)
    reliability_score: float = Field(default=0.5, ge=0, le=1)


class SupplierProduct(BaseModel):
    """The commercial terms for a supplier/product pairing."""

    supplier_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    unit_price: float = Field(ge=0)
    minimum_order_quantity: int = Field(default=1, gt=0)
