"""Smart Inventory Capture View — Voice Inventory Assistant & Camera Scanner."""

import os
import io
import json
import hashlib
from typing import Optional, List
from datetime import datetime, timezone

import streamlit as st

from database.database import Database
from models.inventory import Product
from models.user import User
from models.persistence import AuditEventType
from core.decision_persistence import save_raw_audit_event
from core.billing.subscription_service import SubscriptionService
from core.product_matcher import ProductMatcher
from core.voice_inventory import VoiceInventoryParser
from core.gemini_inventory_vision import GeminiInventoryVisionAnalyzer
from core.inventory_reconciliation import InventoryReconciliationEngine
from core.security import require_admin
from models.inventory_capture import (
    InventoryVoiceCommand,
    InventoryVoiceCommandType,
    ProductMatchStatus,
    InventoryVisionResult,
    InventoryVisionItem,
    ReconciliationItemStatus,
)


def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())


def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


def render_inventory_capture_view(database: Database):
    """Render the Smart Inventory Capture (Voice & Camera Scanner) workstation."""

    # 1. Header
    _h(
        """
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
            <div>
                <div style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 0.12em; text-transform: uppercase;">
                    ⚡ AUTONOMOUS DATA CAPTURE
                </div>
                <h1 style="font-size: 32px; font-weight: 800; letter-spacing: -0.02em; margin: 0; color: #FFFFFF;">
                    Smart Inventory Capture
                </h1>
                <div style="font-size: 14px; color: var(--muted); margin-top: 4px;">
                    Update, query, and reconcile stock with natural voice commands and camera vision.
                </div>
            </div>
            <div style="display: flex; gap: 10px;">
                <div style="padding: 6px 14px; background: rgba(109, 93, 252, 0.12); border: 1px solid rgba(109, 93, 252, 0.3); border-radius: 20px; font-size: 12px; font-weight: 700; color: var(--accent);">
                    🎙️ Voice Engine Active
                </div>
                <div style="padding: 6px 14px; background: rgba(0, 212, 255, 0.12); border: 1px solid rgba(0, 212, 255, 0.3); border-radius: 20px; font-size: 12px; font-weight: 700; color: #00D4FF;">
                    📷 Gemini Vision Active
                </div>
            </div>
        </div>
        """
    )

    # 2. User & Subscription Context
    from ui.components import render_subscription_locked_card
    user = st.session_state.get("authenticated_user")
    user_id = user.id if user else None
    sub_svc = SubscriptionService(database)
    voice_limits = sub_svc.get_voice_limits(user_id)
    vision_limits = sub_svc.get_vision_limits(user_id)
    is_subscribed = sub_svc.is_subscription_active(user_id) if user_id else False
    is_admin = getattr(user, "role", "") == "ADMIN"
    audit_admin, _ = require_admin(user)

    if not is_subscribed and not is_admin:
        render_subscription_locked_card("Smart Inventory Capture (Voice & Camera Scanner)")
        return

    # 3. Main Navigation Tabs
    tabs = st.tabs(
        [
            "🎙️ Voice Inventory Assistant",
            "📷 Camera / Image Scanner & Reconciliation",
        ]
        + (["📋 Discrepancy & Audit Log"] if audit_admin else [])
    )
    tab_voice, tab_camera = tabs[:2]
    tab_history = tabs[2] if audit_admin else None

    # =========================================================================
    # TAB 1: VOICE INVENTORY ASSISTANT
    # =========================================================================
    with tab_voice:
        _render_voice_assistant(database, user, voice_limits)

    # =========================================================================
    # TAB 2: CAMERA / IMAGE SCANNER & RECONCILIATION
    # =========================================================================
    with tab_camera:
        _render_camera_scanner(database, user, vision_limits)

    # =========================================================================
    # TAB 3: AUDIT & DISCREPANCY LOG
    # =========================================================================
    if tab_history:
        with tab_history:
            _render_capture_history(database)


def _render_voice_assistant(database: Database, user: Optional[User], limits: dict):
    """Render the Voice Inventory Assistant with speech parsing and safe preview/confirmation."""
    _h(
        """
        <div class="agent-card" style="margin-bottom: 20px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="font-size: 28px;">🎙️</div>
                <div>
                    <div style="font-size: 18px; font-weight: 700; color: #FFFFFF;">
                        Voice Inventory Assistant
                    </div>
                    <div style="font-size: 13px; color: var(--muted);">
                        Update or query inventory using natural language without manual typing.
                    </div>
                </div>
            </div>
        </div>
        """
    )

    # Example Voice Command Templates
    st.markdown("**⚡ Common Voice Commands Examples:**")
    st.caption("You can speak or type natural commands in your preferred language, e.g. *'Add 20 units of [Product Name]'*, *'Stock 15 bottles received'*, or *'50 packet stock add karo'*.")
    st.write("")

    # Speech / Audio Input & Text Box
    v_col1, v_col2 = st.columns([1, 1.2])

    with v_col1:
        st.markdown("#### 🗣️ Speak or Type Command")
        
        # Audio Input widget (Streamlit audio recording where supported)
        audio_prompt = st.audio_input("🎙️ Record Voice Command", key="voice_audio_record")
        if audio_prompt is not None:
            st.caption("🎙️ Audio received. (Type or select transcript below for exact execution)")

        transcript_val = st.text_input(
            "Natural Language Transcript:",
            value=st.session_state.get("voice_input_text", ""),
            placeholder="e.g., 'Add 20 units of Coca Cola 500ml' or 'What is the stock of SKU AMUL500?'",
            key="voice_text_transcript_input",
        )

        parse_btn = st.button("🔍 Interpret Command", type="primary", key="btn_parse_voice")

    # Command Execution State & Evaluation
    if parse_btn or transcript_val:
        if not transcript_val.strip():
            st.warning("⚠️ Please provide a speech recording or enter a voice transcript.")
            return

        parser = VoiceInventoryParser()
        cmd: InventoryVoiceCommand = parser.parse(transcript_val)
        catalog = database.list_all_products()
        matcher = ProductMatcher(catalog)

        with v_col2:
            st.markdown("#### 🧠 AI Interpretation & Validation")

            # Display Interpretation Card
            cmd_badge_color = "#22C55E" if "QUERY" in cmd.command_type.value else "#6D5DFC"
            _h(
                f"""
                <div class="agent-card" style="border-left: 4px solid {cmd_badge_color};">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="font-size: 11px; font-weight: 800; color: {cmd_badge_color}; text-transform: uppercase; letter-spacing: 0.08em;">
                            DETECTED INTENT: {cmd.command_type.value}
                        </div>
                        <div style="font-size: 11px; font-weight: 700; color: var(--muted);">
                            Confidence: {int(cmd.confidence * 100)}%
                        </div>
                    </div>
                    <div style="font-size: 16px; font-weight: 800; color: #FFFFFF; margin-top: 6px;">
                        "{cmd.raw_transcript}"
                    </div>
                    <div style="font-size: 13px; color: var(--muted); margin-top: 4px;">
                        {cmd.explanation}
                    </div>
                </div>
                """
            )

            # Route by Command Type
            if cmd.command_type == InventoryVoiceCommandType.LOW_STOCK_QUERY:
                _handle_low_stock_query(database)
            elif cmd.command_type == InventoryVoiceCommandType.ALL_PRODUCTS_QUERY:
                _handle_all_products_query(database)
            elif cmd.command_type == InventoryVoiceCommandType.UNKNOWN:
                st.error(f"❌ Unrecognized instruction: {cmd.explanation}")
                st.info("💡 Try phrases like: `'Add 10 units of <Product Name>'` or `'Check stock of <SKU>'`.")
            else:
                # Targeted Product Operations (QUERY, ADD, REMOVE, SET, SUPPLIER_RECEIPT)
                search_term = cmd.sku or cmd.product_identifier or cmd.product_name or ""
                match_res = matcher.match(search_term)

                if match_res.status == ProductMatchStatus.NOT_FOUND:
                    st.error(f"❌ Product not found in catalog matching: **'{search_term}'**")
                    st.caption("Available products in database: " + ", ".join(f"`{p.name}` (`{p.sku}`)" for p in catalog[:6]))
                elif match_res.status == ProductMatchStatus.AMBIGUOUS:
                    st.warning(f"⚠️ Multiple products match '{search_term}'. Please select the intended product:")
                    for cand in match_res.candidates:
                        if st.button(f"👉 {cand.product.name} (SKU: {cand.product.sku}) — Current: {cand.product.current_stock} units", key=f"cand_{cand.product.id}"):
                            st.session_state["selected_voice_product_id"] = cand.product.id
                            st.rerun()
                else:
                    matched_prod = match_res.matched_product
                    if matched_prod:
                        _render_voice_product_action(database, cmd, matched_prod, user)


def _render_voice_product_action(
    database: Database, cmd: InventoryVoiceCommand, product: Product, user: Optional[User]
):
    """Render deterministic preview and confirmation safety workflow for single product action."""
    # Handle read-only queries directly without destructive confirmation
    if cmd.command_type == InventoryVoiceCommandType.QUERY_STOCK:
        _h(
            f"""
            <div class="agent-card" style="background: rgba(0, 212, 255, 0.08); border: 1px solid rgba(0, 212, 255, 0.3);">
                <div style="font-size: 12px; font-weight: 700; color: #00D4FF; text-transform: uppercase;">
                    📦 CURRENT STOCK LEVEL
                </div>
                <div style="font-size: 22px; font-weight: 800; color: #FFFFFF; margin-top: 4px;">
                    {product.name}
                </div>
                <div style="font-size: 13px; color: var(--muted);">SKU: <code>{product.sku}</code></div>
                <div style="display: flex; gap: 20px; margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255, 255, 255, 0.08);">
                    <div><span style="color:var(--muted); font-size:12px;">On-Hand Stock:</span><br/><strong style="font-size:24px; color:#4ADE80;">{product.current_stock} units</strong></div>
                    <div><span style="color:var(--muted); font-size:12px;">Safety Stock:</span><br/><strong style="font-size:20px; color:#F59E0B;">{product.safety_stock} units</strong></div>
                    <div><span style="color:var(--muted); font-size:12px;">Daily Demand:</span><br/><strong style="font-size:20px; color:#FFFFFF;">{product.daily_demand} / day</strong></div>
                </div>
            </div>
            """
        )
        return

    # Handle Mutations (ADD, REMOVE, SET, SUPPLIER_RECEIPT) with strict confirmation
    current_stock = product.current_stock
    qty = cmd.quantity or 0

    if cmd.command_type in {InventoryVoiceCommandType.ADD_STOCK, InventoryVoiceCommandType.SUPPLIER_RECEIPT}:
        delta = qty
        new_stock = current_stock + qty
        action_label = f"➕ ADD STOCK (+{qty} units)"
    elif cmd.command_type == InventoryVoiceCommandType.REMOVE_STOCK:
        delta = -qty
        new_stock = current_stock - qty
        action_label = f"➖ REMOVE STOCK (-{qty} units)"
    elif cmd.command_type == InventoryVoiceCommandType.SET_STOCK:
        delta = qty - current_stock
        new_stock = qty
        action_label = f"⚙️ SET STOCK (Fixed at {qty} units)"
    else:
        return

    if new_stock < 0:
        st.error(f"❌ Cannot remove {qty} units. Current stock is only {current_stock} units (resulting stock would be {new_stock}).")
        return

    # PREVIEW SAFETY CARD (Part 3)
    _h(
        f"""
        <div class="agent-card" style="border: 2px solid var(--accent); background: rgba(109, 93, 252, 0.06); margin-top: 12px;">
            <div style="font-size: 11px; font-weight: 800; color: var(--accent); text-transform: uppercase; letter-spacing: 0.08em;">
                🛡️ CONFIRMATION REQUIRED BEFORE INVENTORY UPDATE
            </div>
            <div style="font-size: 20px; font-weight: 800; color: #FFFFFF; margin-top: 4px;">
                {product.name}
            </div>
            <div style="font-size: 13px; color: var(--muted);">SKU: <code>{product.sku}</code></div>

            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 14px; padding: 12px; background: rgba(0,0,0,0.3); border-radius: 10px;">
                <div>
                    <div style="font-size: 11px; color: var(--muted);">CURRENT STOCK</div>
                    <div style="font-size: 22px; font-weight: 800; color: #FFFFFF;">{current_stock}</div>
                </div>
                <div>
                    <div style="font-size: 11px; color: var(--muted);">CHANGE</div>
                    <div style="font-size: 22px; font-weight: 800; color: {'#4ADE80' if delta >= 0 else '#F87171'};">
                        {'+' if delta > 0 else ''}{delta}
                    </div>
                </div>
                <div>
                    <div style="font-size: 11px; color: var(--muted);">NEW STOCK</div>
                    <div style="font-size: 22px; font-weight: 800; color: #00D4FF;">{new_stock}</div>
                </div>
            </div>
        </div>
        """
    )

    col_cf, col_cn = st.columns([1.5, 1])
    with col_cf:
        if st.button("✅ Confirm & Update Inventory", type="primary", key=f"btn_confirm_voice_{product.id}"):
            try:
                audit_meta = {
                    "source": "VOICE",
                    "product_id": product.id,
                    "sku": product.sku,
                    "product_name": product.name,
                    "previous_quantity": str(current_stock),
                    "new_quantity": str(new_stock),
                    "quantity_delta": str(delta),
                    "raw_transcript": cmd.raw_transcript,
                    "transcript_hash": hashlib.sha256(cmd.raw_transcript.encode("utf-8")).hexdigest(),
                    "confidence": str(cmd.confidence),
                    "user_id": user.id if user else "anonymous",
                }
                prev, updated = database.update_product_stock(product.id, new_stock)
                save_raw_audit_event(
                    database,
                    entity_type="inventory_product",
                    entity_id=product.id,
                    event_type=AuditEventType.INVENTORY_VOICE_MUTATION,
                    metadata=audit_meta,
                )
                st.success(f"✓ Inventory updated! {product.name} stock changed from {prev} to **{updated} units**.")
                st.session_state["voice_input_text"] = ""
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to update inventory: {str(e)}")

    with col_cn:
        if st.button("Cancel", key="btn_cancel_voice_mutation"):
            st.session_state["voice_input_text"] = ""
            st.rerun()


def _handle_low_stock_query(database: Database):
    """Render table of all products below safety stock."""
    products = database.list_all_products()
    low_stock_items = [p for p in products if p.current_stock <= p.safety_stock]

    if not low_stock_items:
        st.success("✓ All catalog products are operating above safety stock thresholds!")
        return

    st.warning(f"⚠️ Found {len(low_stock_items)} items running low or below safety stock:")
    data = []
    for p in low_stock_items:
        data.append({
            "Product": p.name,
            "SKU": p.sku,
            "Current Stock": p.current_stock,
            "Safety Stock": p.safety_stock,
            "Shortage": p.safety_stock - p.current_stock,
            "Daily Demand": p.daily_demand,
        })
    st.dataframe(data, use_container_width=True)


def _handle_all_products_query(database: Database):
    """Render full catalog inventory status."""
    products = database.list_all_products()
    st.markdown(f"**📦 Catalog Inventory Overview ({len(products)} products):**")
    data = []
    for p in products:
        status = "🟢 Healthy" if p.current_stock > p.safety_stock else ("🔴 Stockout" if p.current_stock == 0 else "🟡 Low Stock")
        data.append({
            "Product Name": p.name,
            "SKU": p.sku,
            "Current Stock": p.current_stock,
            "Safety Stock": p.safety_stock,
            "Unit Cost": f"₹{p.unit_cost:.2f}",
            "Daily Demand": p.daily_demand,
            "Status": status,
        })
    st.dataframe(data, use_container_width=True)


# =========================================================================
# TAB 2: CAMERA SCANNER & INVENTORY RECONCILIATION
# =========================================================================
def _render_camera_scanner(database: Database, user: Optional[User], limits: dict):
    """Render Camera & Image Scanner with Gemini Vision and Multi-Product Reconciliation."""
    _h(
        """
        <div class="agent-card" style="margin-bottom: 20px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="font-size: 28px;">📷</div>
                <div>
                    <div style="font-size: 18px; font-weight: 700; color: #FFFFFF;">
                        Camera & Image Inventory Scanner
                    </div>
                    <div style="font-size: 13px; color: var(--muted);">
                        Point your camera at shelves, cartons, or SKU barcodes to audit physical inventory.
                    </div>
                </div>
            </div>
        </div>
        """
    )

    c_col1, c_col2 = st.columns([1, 1.2])

    with c_col1:
        st.markdown("#### 📸 Capture or Upload Image")
        source_mode = st.radio(
            "Input Mode:",
            ["📷 Live Camera Input", "📁 Upload Image File"],
            horizontal=True,
            key="scanner_source_radio",
        )

        image_bytes: Optional[bytes] = None

        if source_mode == "📷 Live Camera Input":
            cam_file = st.camera_input("Take a photo of product shelf or barcode label", key="cam_input_feed")
            if cam_file is not None:
                image_bytes = cam_file.getvalue()
        elif source_mode == "📁 Upload Image File":
            up_file = st.file_uploader("Upload product shelf or carton photo (JPG, PNG, WEBP)", type=["jpg", "jpeg", "png", "webp"], key="cam_upload_file")
            if up_file is not None:
                image_bytes = up_file.getvalue()

        if image_bytes:
            st.image(image_bytes, caption="📸 Scanned Frame", use_container_width=True)

        analyze_btn = st.button("⚡ Analyze Visual Inventory", type="primary", key="btn_analyze_vision")

    with c_col2:
        st.markdown("#### 📊 Vision Extraction & Reconciliation")

        if analyze_btn and image_bytes:
            with st.spinner("🤖 Gemini Vision inspecting image for products, SKUs, and visible quantities..."):
                analyzer = GeminiInventoryVisionAnalyzer()
                vision_res = analyzer.analyze_image(image_bytes)
                st.session_state["latest_vision_result"] = vision_res

        vision_res: Optional[InventoryVisionResult] = st.session_state.get("latest_vision_result")

        if vision_res:
            _render_reconciliation_report(database, vision_res, user)
        else:
            _h(
                """
                <div class="agent-card" style="text-align: center; padding: 40px 20px;">
                    <div style="font-size: 36px; margin-bottom: 8px;">📷</div>
                    <div style="font-size: 16px; font-weight: 700; color: #FFFFFF;">No Scan Active</div>
                    <div style="font-size: 13px; color: var(--muted); margin-top: 4px;">
                        Take a photo or upload an image to inspect inventory counts and discrepancies.
                    </div>
                </div>
                """
            )


def _render_reconciliation_report(
    database: Database, vision_res: InventoryVisionResult, user: Optional[User]
):
    """Render multi-product reconciliation table with interactive discrepancy checkboxes."""
    recon_engine = InventoryReconciliationEngine(database)
    report = recon_engine.generate_report(vision_res)

    _h(
        f"""
        <div class="agent-card" style="border-left: 4px solid #00D4FF; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="font-size: 11px; font-weight: 800; color: #00D4FF; text-transform: uppercase; letter-spacing: 0.08em;">
                    ✓ {report.total_detected} PRODUCTS DETECTED IN IMAGE
                </div>
                <div style="font-size: 11px; color: var(--muted);">
                    Discrepancies: <strong style="color: #F59E0B;">{report.total_discrepancies}</strong> | Matched: <strong style="color: #4ADE80;">{report.total_matched}</strong>
                </div>
            </div>
        </div>
        """
    )

    st.markdown("**🔍 Discrepancy Reconciliation Table:**")
    st.caption("Select the items you want to reconcile into the system inventory database:")

    selected_ids = []

    for item in report.items:
        with st.container():
            c_chk, c_info, c_stat = st.columns([0.4, 2.2, 1])

            with c_chk:
                is_selected = st.checkbox(
                    "Select",
                    value=item.selected_for_reconciliation,
                    key=f"chk_{item.item_id}",
                    label_visibility="collapsed",
                )
                if is_selected and item.product and item.observed_quantity is not None:
                    selected_ids.append(item.item_id)

            with c_info:
                st.markdown(f"**{item.detected_name}** `({item.detected_sku or 'No SKU'})`")
                if item.observed_quantity is not None and item.system_stock is not None:
                    diff_str = f"{item.discrepancy:+d} units"
                    diff_color = "#22C55E" if item.discrepancy == 0 else ("#F59E0B" if item.discrepancy > 0 else "#F87171")
                    st.markdown(
                        f"<span style='font-size:12px; color:var(--muted);'>System: <strong>{item.system_stock}</strong> | Observed: <strong>{item.observed_quantity}</strong> | Difference: <strong style='color:{diff_color};'>{diff_str}</strong></span>",
                        unsafe_allow_html=True,
                    )
                elif item.status == ReconciliationItemStatus.UNQUANTIFIABLE:
                    st.markdown("<span style='font-size:12px; color:#F59E0B;'>⚠️ Quantity could not be reliably determined from image.</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='font-size:12px; color:#F87171;'>❌ Unregistered product not found in database.</span>", unsafe_allow_html=True)

                if item.evidence:
                    st.caption(f"Evidence: {item.evidence}")

            with c_stat:
                if item.status == ReconciliationItemStatus.MATCH:
                    st.markdown("<span style='color:#22C55E; font-weight:700; font-size:12px;'>✓ Stock Aligned</span>", unsafe_allow_html=True)
                elif item.status == ReconciliationItemStatus.DEFICIT:
                    st.markdown("<span style='color:#F87171; font-weight:700; font-size:12px;'>⚠️ Deficit Found</span>", unsafe_allow_html=True)
                elif item.status == ReconciliationItemStatus.SURPLUS:
                    st.markdown("<span style='color:#F59E0B; font-weight:700; font-size:12px;'>📈 Surplus Found</span>", unsafe_allow_html=True)
                elif item.status == ReconciliationItemStatus.UNQUANTIFIABLE:
                    st.markdown("<span style='color:var(--muted); font-size:12px;'>❓ Unquantifiable</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color:#F87171; font-size:12px;'>🚫 Unregistered</span>", unsafe_allow_html=True)

            st.divider()

    # Reconcile Action Button
    col_apply, col_reset = st.columns([2, 1])
    with col_apply:
        btn_label = f"⚡ Reconcile {len(selected_ids)} Selected Products" if selected_ids else "Reconcile Selected Products"
        if st.button(btn_label, type="primary", disabled=len(selected_ids) == 0, key="btn_apply_reconciliation"):
            with st.spinner("Applying atomic database reconciliation updates..."):
                res = recon_engine.apply_reconciliation(report, selected_ids, user.id if user else None)
                if res["status"] == "success":
                    st.success(f"✓ Successfully reconciled {res['adjusted_count']} products in the database!")
                    st.session_state["latest_vision_result"] = None
                    st.session_state["demo_scan_active"] = False
                    st.rerun()
                else:
                    st.warning("No changes were applied.")

    with col_reset:
        if st.button("Clear / Cancel Scan", key="btn_clear_scan"):
            st.session_state["latest_vision_result"] = None
            st.session_state["demo_scan_active"] = False
            st.rerun()


# =========================================================================
# TAB 3: AUDIT HISTORY
# =========================================================================
def _render_capture_history(database: Database):
    """Render recent voice & vision capture audit records."""
    auth_ok, message = require_admin(st.session_state.get("authenticated_user"))
    if not auth_ok:
        st.error(message)
        return

    _h(
        """
        <div class="agent-card" style="margin-bottom: 20px;">
            <div style="font-size: 18px; font-weight: 700; color: #FFFFFF;">
                📋 Smart Capture Audit Log
            </div>
            <div style="font-size: 13px; color: var(--muted);">
                Immutable cryptographic ledger of voice mutations and camera reconciliations.
            </div>
        </div>
        """
    )

    all_audits = database.list_audit_events()
    capture_audits = [
        a for a in all_audits
        if a["event_type"] in {
            AuditEventType.INVENTORY_VOICE_MUTATION.value,
            AuditEventType.INVENTORY_CAMERA_RECONCILIATION.value,
            AuditEventType.INVENTORY_STOCK_ADJUSTMENT.value,
        }
    ]

    if not capture_audits:
        st.info("ℹ️ No voice mutations or visual reconciliations have been recorded yet.")
        return

    for audit in capture_audits[:15]:
        ev_type = audit["event_type"]
        meta = json.loads(audit["metadata_json"]) if audit["metadata_json"] else {}
        created = audit["created_at"]

        badge_color = "#6D5DFC" if "VOICE" in ev_type else "#00D4FF"
        icon = "🎙️" if "VOICE" in ev_type else "📷"

        _h(
            f"""
            <div class="agent-card" style="margin-bottom: 12px; border-left: 3px solid {badge_color};">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-size: 12px; font-weight: 800; color: {badge_color};">
                        {icon} {ev_type}
                    </div>
                    <div style="font-size: 11px; color: var(--muted);">
                        🕒 {created}
                    </div>
                </div>
                <div style="font-size: 14px; font-weight: 700; color: #FFFFFF; margin-top: 4px;">
                    {meta.get('product_name', meta.get('records_summary', 'Inventory Adjustment'))}
                </div>
                <div style="font-size: 12px; color: var(--muted); margin-top: 2px;">
                    {f"Transcript: <em>'{meta.get('raw_transcript')}'</em> | " if meta.get('raw_transcript') else ""}
                    {f"Change: {meta.get('previous_quantity')} ➔ <strong>{meta.get('new_quantity')} units</strong> ({meta.get('quantity_delta'):+} delta)" if meta.get('previous_quantity') else ""}
                </div>
            </div>
            """
        )
