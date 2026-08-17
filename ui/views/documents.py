"""Document and Invoice Processor View."""
import streamlit as st
from database.database import Database
from core.document_processor import DocumentProcessor
from core.billing.subscription_service import SubscriptionService
from models.inventory import Product
from ui.components import render_subscription_locked_card


def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())


def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


def render_documents_view(database: Database):
    """Render Document & Invoice processing workstation."""
    user = st.session_state.get("authenticated_user")
    user_id = user.id if user else None
    sub_svc = SubscriptionService(database)
    processor = DocumentProcessor()
    is_subscribed = sub_svc.is_subscription_active(user_id) if user_id else False
    is_admin = getattr(user, "role", "") == "ADMIN"

    _h(
        """
        <div style="margin-bottom: 24px;">
            <div style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 0.12em; text-transform: uppercase;">
                📄 INTELLIGENT DOCUMENT AI
            </div>
            <h1 style="font-size: 32px; font-weight: 800; letter-spacing: -0.02em; margin: 0; color: #FFFFFF;">
                Inventory Document Processor
            </h1>
            <div style="font-size: 14px; color: var(--muted); margin-top: 4px;">
                Upload supplier invoices, purchase receipts, and stock sheets to automatically extract inventory line items.
            </div>
        </div>
        """
    )

    if not is_subscribed and not is_admin:
        render_subscription_locked_card("Invoice & Document OCR")
        return

    businesses = database.list_businesses(user_id)
    if not businesses:
        _h(
            """
            <div class="agent-card" style="text-align: center; padding: 40px 20px;">
                <div style="font-size: 38px; margin-bottom: 8px;">🏪</div>
                <div style="font-size: 18px; font-weight: 700; color: #FFFFFF;">No Business Profile Found</div>
                <div style="font-size: 13px; color: var(--muted); margin: 6px auto 16px auto; max-width: 450px;">
                    Please add your first business profile in Settings & Catalog to assign uploaded invoices and stock receipts.
                </div>
            </div>
            """
        )
        if st.button("⚙️ Go to Settings & Add Business Profile", type="primary"):
            st.session_state["pending_nav_page"] = "⚙️ Settings & Catalog"
            st.rerun()
        return

    b_options = {b.name: b.id for b in businesses}
    sel_biz = st.selectbox("Assign to Business:", list(b_options.keys()), key="doc_biz_sel")
    business_id = b_options[sel_biz]

    col_up, col_res = st.columns([1, 1.3])

    with col_up:
        with st.container(border=True):
            st.markdown("### 📤 Upload Document")
            st.caption("Supported formats: PDF, CSV, XLSX, PNG, JPG (Max 10MB)")

            up_file = st.file_uploader(
                "Select File",
                type=["pdf", "csv", "xlsx", "png", "jpg", "jpeg", "webp"],
                key="doc_uploader_widget",
            )

            if up_file is not None:
                file_bytes = up_file.getvalue()
                filename = up_file.name

                is_valid, val_msg = processor.validate_file(filename, file_bytes)
                if not is_valid:
                    st.error(f"❌ {val_msg}")
                else:
                    st.success(f"✓ File '{filename}' ({len(file_bytes)/1024:.1f} KB) ready.")

                    if st.button("⚡ Process & Extract Inventory Lines", type="primary", key="btn_proc_doc"):
                        # Metered usage check
                        ok_usage, use_msg, _, _ = sub_svc.check_and_increment_usage(user_id, "documents_analyzed")
                        if not ok_usage:
                            st.error(use_msg)
                        else:
                            with st.spinner("🤖 Extracting product line items, SKUs, quantities, and prices..."):
                                res = processor.extract_inventory_data(filename, file_bytes)
                                st.session_state["latest_doc_result"] = res
                                st.session_state["latest_doc_filename"] = filename
                                processor.save_file_securely(user_id, filename, file_bytes)
                                st.rerun()

    with col_res:
        st.markdown("### 📊 Extracted Inventory Lines")
        doc_res = st.session_state.get("latest_doc_result")

        if doc_res:
            st.success(f"✓ Extracted {len(doc_res.items)} items from `{st.session_state.get('latest_doc_filename', 'document')}`")

            table_data = []
            for item in doc_res.items:
                table_data.append({
                    "Product Name": item.product_name,
                    "SKU": item.sku or "—",
                    "Qty": item.quantity,
                    "Unit Price (₹)": f"₹{item.unit_price:.2f}" if item.unit_price else "—",
                    "Total (₹)": f"₹{item.total_amount:.2f}" if item.total_amount else "—",
                    "Confidence": f"{item.confidence * 100:.0f}%",
                })

            st.dataframe(table_data, use_container_width=True)

            if st.button("📥 Import All Extracted Items into Business Catalog", type="primary", key="btn_import_extracted"):
                imported_count = 0
                for item in doc_res.items:
                    prod = Product(
                        id=f"prod_{item.product_name.lower().replace(' ', '_')[:16]}",
                        business_id=business_id,
                        user_id=user_id,
                        sku=item.sku or item.product_name[:6].upper(),
                        name=item.product_name,
                        current_stock=int(item.quantity) if item.quantity else 0,
                        daily_demand=5.0,
                        safety_stock=10,
                        unit_cost=float(item.unit_price) if item.unit_price else 100.0,
                    )
                    database.create_product(prod)
                    imported_count += 1

                st.success(f"✓ Successfully imported {imported_count} products into your catalog!")
                st.session_state.pop("latest_doc_result", None)
                st.rerun()
        else:
            _h(
                """
                <div class="agent-card" style="text-align: center; padding: 40px 20px;">
                    <div style="font-size: 36px; margin-bottom: 8px;">📄</div>
                    <div style="font-size: 16px; font-weight: 700; color: #FFFFFF;">No Document Extracted</div>
                    <div style="font-size: 13px; color: var(--muted); margin-top: 4px;">
                        Upload a file on the left and click 'Process' to review extracted line items.
                    </div>
                </div>
                """
            )
