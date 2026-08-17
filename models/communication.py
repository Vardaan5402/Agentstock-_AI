"""Supplier communication, order drafts, and dispatch tracking models."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class CommType(str, Enum):
    """Supported supplier communication channels."""
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    PHONE_CALL = "PHONE_CALL"


class CommStatus(str, Enum):
    """Communication message delivery statuses."""
    DRAFT = "DRAFT"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OrderDraft(BaseModel):
    """Structured purchase order communication draft."""
    order_id: str
    business_name: str
    supplier_name: str
    supplier_phone: str
    supplier_email: Optional[str] = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    total_cost: float = 0.0
    notes: Optional[str] = None
    subject: str = ""
    formatted_body: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SupplierCommunication(BaseModel):
    """Persisted communication log record."""
    id: str
    business_id: str
    user_id: str
    supplier_id: str
    comm_type: str = CommType.IN_APP.value
    subject: Optional[str] = None
    body: str
    status: str = CommStatus.SENT.value
    order_reference: Optional[str] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    duration_seconds: Optional[int] = None
    metadata_json: Optional[str] = "{}"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
