import os
import re
import secrets
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from uuid import uuid4
from database.database import Database
from models.communication import (
    CommType,
    CommStatus,
    OrderDraft,
    SupplierCommunication,
)
from models.business import Business
from models.supplier import Supplier
from models.inventory import Product
from core.config import get_smtp_config


class SupplierCommunicationService:
    """Manages order generation and multi-channel supplier dispatch."""

    def __init__(self, database: Database):
        self.database = database

    def generate_order_draft(
        self,
        business_name: str,
        supplier: Supplier,
        product_name: str,
        sku: str,
        quantity: int,
        unit_price: float,
        total_cost: float,
        notes: Optional[str] = None,
    ) -> OrderDraft:
        """Create a professional, clear purchase order communication draft."""
        order_id = f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        subject = f"Purchase Order {order_id} from {business_name}"

        body = (
            f"Hello {supplier.name},\n\n"
            f"We would like to place an order for the following items:\n\n"
            f"• Product: {product_name} (SKU: {sku})\n"
            f"• Quantity: {quantity} units\n"
            f"• Agreed Unit Price: ₹{unit_price:,.2f}\n"
            f"• Total Order Value: ₹{total_cost:,.2f}\n\n"
            f"Please confirm availability, expected delivery date, and invoice details.\n\n"
            f"{f'Special Notes: {notes}' + chr(10) + chr(10) if notes else ''}"
            f"Thank you,\n"
            f"{business_name}\n"
            f"Generated via AgentStock AI"
        )

        return OrderDraft(
            order_id=order_id,
            business_name=business_name,
            supplier_name=supplier.name,
            supplier_phone=supplier.phone,
            supplier_email=supplier.email,
            items=[{
                "product_name": product_name,
                "sku": sku,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_cost": total_cost,
            }],
            total_cost=total_cost,
            notes=notes,
            subject=subject,
            formatted_body=body,
        )

    def get_whatsapp_url(self, phone: str, message: str) -> str:
        """Generate official WhatsApp click-to-chat deep link with prefilled text."""
        clean_phone = re.sub(r"[^\d+]", "", phone.strip())
        if clean_phone.startswith("+"):
            clean_phone = clean_phone[1:]

        encoded_msg = urllib.parse.quote(message)
        return f"https://wa.me/{clean_phone}?text={encoded_msg}"

    def get_phone_call_url(self, phone: str) -> str:
        """Generate standard browser telephone dialer link."""
        clean_phone = re.sub(r"[^\d+]", "", phone.strip())
        return f"tel:{clean_phone}"

    def send_email_order(
        self,
        draft: OrderDraft,
        recipient_email: str,
        user_id: str,
        business_id: str,
        supplier_id: str,
    ) -> Tuple[bool, str]:
        """Dispatch order via SMTP email if configured, or record as dispatched."""
        if not recipient_email or "@" not in recipient_email:
            return False, "Invalid recipient email address."

        smtp = get_smtp_config()
        if smtp.get("host") and smtp.get("username"):
            try:
                msg = MIMEMultipart()
                msg["From"] = smtp["from_email"]
                msg["To"] = recipient_email
                msg["Subject"] = draft.subject
                msg.attach(MIMEText(draft.formatted_body, "plain"))

                with smtplib.SMTP(smtp["host"], smtp["port"], timeout=10) as server:
                    server.starttls()
                    server.login(smtp["username"], smtp["password"])
                    server.send_message(msg)

                status = CommStatus.DELIVERED.value
                msg_status = "Email sent successfully via SMTP server."
            except Exception as e:
                status = CommStatus.FAILED.value
                msg_status = f"SMTP dispatch error: {str(e)}"
        else:
            # Standalone logged dispatch
            status = CommStatus.SENT.value
            msg_status = "Order email prepared and logged to communication history."

        comm = SupplierCommunication(
            id=uuid4().hex,
            business_id=business_id,
            user_id=user_id,
            supplier_id=supplier_id,
            comm_type=CommType.EMAIL.value,
            subject=draft.subject,
            body=draft.formatted_body,
            status=status,
            order_reference=draft.order_id,
            sender=smtp.get("from_email", "orders@agentstock.ai"),
            recipient=recipient_email,
        )
        self.database.create_supplier_communication(comm)
        return True, msg_status

    def record_communication(
        self,
        business_id: str,
        user_id: str,
        supplier_id: str,
        comm_type: CommType,
        body: str,
        subject: Optional[str] = None,
        order_reference: Optional[str] = None,
        recipient: Optional[str] = None,
        status: CommStatus = CommStatus.SENT,
    ) -> SupplierCommunication:
        """Persist a supplier interaction to the immutable communication audit log."""
        comm = SupplierCommunication(
            id=uuid4().hex,
            business_id=business_id,
            user_id=user_id,
            supplier_id=supplier_id,
            comm_type=comm_type.value,
            subject=subject,
            body=body,
            status=status.value,
            order_reference=order_reference,
            recipient=recipient,
        )
        self.database.create_supplier_communication(comm)
        return comm


def secrets_hex(n: int) -> str:
    import secrets
    return secrets.token_hex(n)
