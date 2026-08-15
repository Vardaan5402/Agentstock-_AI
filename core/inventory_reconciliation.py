"""Deterministic Inventory Reconciliation Engine comparing Visual Scans with System Database."""

from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime, timezone
from database.database import Database
from models.inventory import Product
from models.persistence import AuditEventType
from core.decision_persistence import save_raw_audit_event
from models.inventory_capture import (
    InventoryVisionResult,
    InventoryVisionItem,
    InventoryReconciliationItem,
    InventoryReconciliationReport,
    ReconciliationItemStatus,
    ProductMatchStatus,
)
from core.product_matcher import ProductMatcher


class InventoryReconciliationEngine:
    """Builds discrepancy reports and applies verified visual inventory adjustments."""

    def __init__(self, database: Database):
        self.database = database

    def generate_report(
        self, vision_result: InventoryVisionResult, business_id: Optional[str] = None
    ) -> InventoryReconciliationReport:
        """Compare observed vision items against persisted catalog stock."""
        if business_id:
            catalog = self.database.list_products(business_id)
        else:
            catalog = self.database.list_all_products()

        matcher = ProductMatcher(catalog)
        reconciled_items: List[InventoryReconciliationItem] = []
        discrepancies = 0
        matched_count = 0

        for idx, item in enumerate(vision_result.items):
            item_id = f"recon_{idx + 1}_{uuid4().hex[:6]}"
            search_query = item.sku or item.barcode or item.product_name or ""
            match_res = matcher.match(search_query)

            matched_prod = match_res.matched_product
            detected_name = item.product_name or (matched_prod.name if matched_prod else "Unknown Product")
            detected_sku = item.sku or (matched_prod.sku if matched_prod else None)
            detected_barcode = item.barcode

            if matched_prod is None:
                status = ReconciliationItemStatus.UNREGISTERED
                sys_stock = None
                disc = None
            elif item.observed_quantity is None:
                status = ReconciliationItemStatus.UNQUANTIFIABLE
                sys_stock = matched_prod.current_stock
                disc = None
            else:
                sys_stock = matched_prod.current_stock
                disc = item.observed_quantity - sys_stock
                if disc == 0:
                    status = ReconciliationItemStatus.MATCH
                    matched_count += 1
                elif disc > 0:
                    status = ReconciliationItemStatus.SURPLUS
                    discrepancies += 1
                else:
                    status = ReconciliationItemStatus.DEFICIT
                    discrepancies += 1

            reconciled_items.append(
                InventoryReconciliationItem(
                    item_id=item_id,
                    product=matched_prod,
                    detected_name=detected_name,
                    detected_sku=detected_sku,
                    detected_barcode=detected_barcode,
                    observed_quantity=item.observed_quantity,
                    system_stock=sys_stock,
                    discrepancy=disc,
                    confidence=item.confidence,
                    evidence=item.evidence or "",
                    status=status,
                    selected_for_reconciliation=(status in {ReconciliationItemStatus.SURPLUS, ReconciliationItemStatus.DEFICIT}),
                )
            )

        return InventoryReconciliationReport(
            reconciliation_id=f"rep_{uuid4().hex[:10]}",
            image_hash=vision_result.image_hash,
            items=reconciled_items,
            total_detected=len(vision_result.items),
            total_discrepancies=discrepancies,
            total_matched=matched_count,
        )

    def apply_reconciliation(
        self,
        report: InventoryReconciliationReport,
        selected_item_ids: List[str],
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atomically update product stock for selected items and record immutable audit event."""
        to_adjust = []
        audit_records = []

        for item in report.items:
            if item.item_id in selected_item_ids and item.product and item.observed_quantity is not None:
                to_adjust.append({
                    "product_id": item.product.id,
                    "new_stock": item.observed_quantity,
                })
                audit_records.append({
                    "product_id": item.product.id,
                    "sku": item.product.sku,
                    "name": item.product.name,
                    "previous_stock": item.system_stock,
                    "new_stock": item.observed_quantity,
                    "delta": item.discrepancy,
                    "confidence": item.confidence,
                })

        if not to_adjust:
            return {"status": "no_changes", "adjusted_count": 0, "records": []}

        # Apply atomic batch reconciliation in database
        results = self.database.batch_reconcile_inventory(to_adjust)

        # Record immutable audit event
        save_raw_audit_event(
            self.database,
            entity_type="inventory_reconciliation",
            entity_id=report.reconciliation_id,
            event_type=AuditEventType.INVENTORY_CAMERA_RECONCILIATION,
            metadata={
                "image_hash": report.image_hash,
                "user_id": user_id or "anonymous",
                "adjusted_count": str(len(results)),
                "records_summary": f"Reconciled {len(results)} items: " + ", ".join(f"{r['sku']}:{r['delta']:+d}" for r in results),
            },
        )

        return {
            "status": "success",
            "adjusted_count": len(results),
            "records": results,
            "reconciliation_id": report.reconciliation_id,
        }
