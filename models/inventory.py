"""Product, sales, and purchase models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PurchaseStatus(str, Enum):
    """Allowed lifecycle states for a purchase."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    SENT = "SENT"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class Product(BaseModel):
    """A stock keeping unit owned by a business."""

    id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    user_id: Optional[str] = None
    sku: str = Field(min_length=1)
    name: str = Field(min_length=1)
    current_stock: int = Field(ge=0)
    unit_cost: float = Field(ge=0)
    daily_demand: float = Field(ge=0)
    safety_stock: int = Field(default=0, ge=0)


class SalesRecord(BaseModel):
    """A recorded sale of a product."""

    id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    sale_date: datetime
    revenue: float | None = Field(default=None, ge=0)


class Purchase(BaseModel):
    """A proposed or completed supplier purchase."""

    id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    supplier_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)
    status: PurchaseStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
