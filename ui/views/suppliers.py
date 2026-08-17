"""Comprehensive Supplier Management, Commercial Directory & PO Dispatch Suite."""
import os
from uuid import uuid4
import streamlit as st
from database.database import Database
from models.supplier import Supplier, SupplierProduct
from models.communication import CommType, CommStatus
from core.billing.subscription_service import SubscriptionService
from core.supplier_communication import SupplierCommunicationService
from ui.views.auth import get_current_user
from ui.components import render_section_header, render_kpi_card


def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())


def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


def render_suppliers_view(database: Database):
    """Render full Supplier Management, Commercial Terms, and PO Dispatch Suite."""
    user = get_current_user(database)
    if not user:
        st.warning("Please sign in to manage suppliers and purchase orders.")
        return
    user_id = user.id
    comm_svc = SupplierCommunicationService(database)

    _h(
        """
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
            <div>
                <div style="font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 0.12em; text-transform: uppercase;">
                    🚚 SUPPLY CHAIN NETWORK
                </div>
                <h1 style="font-size: 32px; font-weight: 800; letter-spacing: -0.02em; margin: 0; color: #FFFFFF;">
                    Supplier Directory & Dispatch
                </h1>
                <div style="font-size: 14px; color: var(--muted); margin-top: 4px;">
                    Manage supplier relationships, delivery contacts, commercial terms, and instant PO dispatch.
                </div>
            </div>
        </div>
        """
    )

    from ui.components import render_subscription_locked_card
    sub_svc = SubscriptionService(database)
    is_subscribed = sub_svc.is_subscription_active(user_id) if user_id else False
    is_admin = getattr(user, "role", "") == "ADMIN"

    if not is_subscribed and not is_admin:
        render_subscription_locked_card("Supplier Directory & Purchase Orders")
        return

    businesses = database.list_businesses(user_id)
    if not businesses:
        _h(
            """
            <div class="agent-card" style="text-align: center; padding: 40px 20px;">
                <div style="font-size: 38px; margin-bottom: 8px;">🏪</div>
                <div style="font-size: 18px; font-weight: 700; color: #FFFFFF;">No Business Profile Configured</div>
                <div style="font-size: 13px; color: var(--muted); margin: 6px auto 16px auto; max-width: 450px;">
                    Please add your first business profile in Settings & Catalog before creating and managing suppliers.
                </div>
            </div>
            """
        )
        if st.button("⚙️ Go to Settings & Add Business Profile", type="primary", key="btn_sup_add_biz"):
            st.session_state["pending_nav_page"] = "⚙️ Settings & Catalog"
            st.rerun()
        return

    b_options = {b.name: b.id for b in businesses}
    selected_biz_name = st.selectbox("Active Business Location:", list(b_options.keys()), key="sup_biz_select")
    active_biz_id = b_options[selected_biz_name]

    tab_list, tab_add, tab_dispatch, tab_comms = st.tabs([
        "👥 Supplier Directory",
        "➕ Add New Supplier",
        "📦 Create & Dispatch Purchase Order",
        "📜 Communication History",
    ])

    # =========================================================================
    # TAB 1: SUPPLIER DIRECTORY
    # =========================================================================
    with tab_list:
        _render_supplier_list(database, active_biz_id, user_id)

    # =========================================================================
    # TAB 2: ADD NEW SUPPLIER
    # =========================================================================
    with tab_add:
        _render_add_supplier(database, active_biz_id, user_id)

    # =========================================================================
    # TAB 3: CREATE & DISPATCH PURCHASE ORDER
    # =========================================================================
    with tab_dispatch:
        _render_po_dispatcher(database, active_biz_id, user_id, comm_svc)

    # =========================================================================
    # TAB 4: COMMUNICATION HISTORY
    # =========================================================================
    with tab_comms:
        _render_communication_history(database, active_biz_id, user_id)


def _render_supplier_list(database: Database, business_id: str, user_id: str | None):
    """Render list of active and archived suppliers."""
    show_archived = st.checkbox("Show Archived Suppliers", value=False, key="sup_show_archived")
    suppliers = database.list_suppliers(business_id, user_id, include_archived=show_archived)

    if not suppliers:
        st.info("ℹ️ No suppliers found for this business. Click **'Add New Supplier'** to add your first supplier.")
        return

    st.markdown(f"**Showing {len(suppliers)} Suppliers:**")

    for sup in suppliers:
        archived_tag = '<span style="color:#EF4444; font-size:11px; font-weight:700;">[ARCHIVED]</span>' if sup.is_archived else ''
        status_color = "#94A3B8" if sup.is_archived else "#22C55E"

        with st.container(border=True):
            c_info, c_terms, c_act = st.columns([2, 1.5, 1.2])

            with c_info:
                st.markdown(f"### {sup.name} {archived_tag}")
                if sup.company_name:
                    st.caption(f"Company: {sup.company_name} • Category: {sup.supplier_category or 'General'}")
                st.markdown(
                    f"📞 **Phone:** `{sup.phone}` | ✉️ **Email:** `{sup.email or 'None'}`<br/>"
                    f"📍 **Address:** {sup.address or 'Not specified'}<br/>"
                    f"🚚 **Delivery Contact:** {sup.delivery_person_name or 'Not assigned'} ({sup.delivery_person_phone or '—'})",
                    unsafe_allow_html=True,
                )

            with c_terms:
                st.markdown("**Commercial Performance:**")
                st.markdown(
                    f"⏱️ **Lead Time:** {sup.lead_time_days:.1f} days<br/>"
                    f"⭐ **Reliability:** {sup.reliability_score * 100:.0f}%<br/>"
                    f"💳 **Terms:** {sup.payment_terms or 'Net 30'}<br/>"
                    f"🏛️ **GST/Tax ID:** `{sup.gst_id or '—'}`",
                    unsafe_allow_html=True,
                )

            with c_act:
                st.markdown("**Actions:**")
                if not sup.is_archived:
                    if st.button("📦 Create Order", key=f"btn_order_{sup.id}", type="primary"):
                        st.session_state["target_dispatch_supplier_id"] = sup.id
                        st.session_state["pending_suppliers_tab"] = "📦 Create & Dispatch Purchase Order"
                        st.rerun()

                    if st.button("📁 Archive Supplier", key=f"btn_arc_{sup.id}"):
                        database.archive_supplier(sup.id, user_id)
                        st.success(f"✓ Supplier '{sup.name}' archived.")
                        st.rerun()
                else:
                    if st.button("♻️ Restore Supplier", key=f"btn_rest_{sup.id}"):
                        database.restore_supplier(sup.id, user_id)
                        st.success(f"✓ Supplier '{sup.name}' restored.")
                        st.rerun()


def _render_add_supplier(database: Database, business_id: str, user_id: str | None):
    """Render Add Supplier form with full commercial contact fields."""
    st.markdown("### ➕ Register New Supplier")
    st.caption("All commercial terms and delivery details will be used by the AI Decision Engine and PO Dispatcher.")

    with st.form("add_supplier_full_form"):
        col1, col2 = st.columns(2)
        with col1:
            s_name = st.text_input("Supplier Contact Name *", placeholder="e.g. Ramesh Kumar")
            s_company = st.text_input("Business / Company Name *", placeholder="e.g. National Dairy & Beverages Ltd")
            s_phone = st.text_input("Phone Number (REQUIRED for WhatsApp / Calling) *", placeholder="+91 9876543210")
            s_email = st.text_input("Email Address", placeholder="orders@nationaldairy.com")
            s_address = st.text_area("Supplier Warehouse / Dispatch Address", placeholder="123 Industrial Area, Sector 4")

        with col2:
            s_del_name = st.text_input("Delivery Person's Name", placeholder="e.g. Suresh (Driver)")
            s_del_phone = st.text_input("Delivery Person's Phone Number", placeholder="+91 9123456780")
            s_gst = st.text_input("GST / Tax Identification Number", placeholder="07AAAAA0000A1Z5")
            s_cat = st.selectbox("Supplier Category", ["Dairy & Cold Storage", "Dry Grocery & Staples", "Beverages", "Packaging", "General"])

            c_lt, c_rel = st.columns(2)
            s_lead = c_lt.number_input("Average Lead Time (Days)", min_value=0.0, value=2.0, step=0.5)
            s_rel = c_rel.number_input("Reliability Score (0.0 to 1.0)", min_value=0.0, max_value=1.0, value=0.90, step=0.05)
            s_terms = st.selectbox("Payment Terms", ["Immediate / COD", "Net 7 Days", "Net 15 Days", "Net 30 Days", "Advance Payment"])

        s_notes = st.text_input("Special Notes / Order Instructions", placeholder="e.g. Requires morning delivery before 10 AM")

        submit_add = st.form_submit_button("Save Supplier to Database ➔", type="primary")

        if submit_add:
            clean_name = s_name.strip()
            clean_company = s_company.strip()
            clean_phone = s_phone.strip()

            if not clean_name or not clean_company or not clean_phone:
                st.error("Supplier Contact Name, Company Name, and Phone Number are strictly required.")
                return

            new_sup = Supplier(
                id=uuid4().hex,
                business_id=business_id,
                user_id=user_id,
                name=clean_name,
                company_name=s_company.strip() if s_company else None,
                phone=clean_phone,
                email=s_email.strip() if s_email else None,
                address=s_address.strip() if s_address else None,
                delivery_person_name=s_del_name.strip() if s_del_name else None,
                delivery_person_phone=s_del_phone.strip() if s_del_phone else None,
                gst_id=s_gst.strip() if s_gst else None,
                payment_terms=s_terms,
                supplier_category=s_cat,
                notes=s_notes.strip() if s_notes else None,
                lead_time_days=float(s_lead),
                reliability_score=float(s_rel),
            )
            database.create_supplier(new_sup)
            st.success(f"✓ Supplier '{new_sup.name}' registered successfully!")
            st.rerun()


def _render_po_dispatcher(
    database: Database, business_id: str, user_id: str | None, comm_svc: SupplierCommunicationService
):
    """Render interactive PO Drafting and Multi-Channel Dispatch Suite."""
    st.markdown("### 📦 Generate & Dispatch Purchase Order")

    suppliers = database.list_suppliers(business_id, user_id)
    products = database.list_products(business_id, user_id)

    if not suppliers:
        st.warning("Please add at least one supplier first.")
        return
    if not products:
        st.warning("Please add products in Settings & Catalog first.")
        return

    sup_map = {f"{s.name} ({s.phone})": s for s in suppliers}
    prod_map = {f"{p.name} (SKU: {p.sku}) — Stock: {p.current_stock}": p for p in products}

    c1, c2 = st.columns(2)
    with c1:
        sel_sup_str = st.selectbox("Select Supplier:", list(sup_map.keys()), key="po_sel_sup")
        selected_supplier = sup_map[sel_sup_str]
    with c2:
        sel_prod_str = st.selectbox("Select Product:", list(prod_map.keys()), key="po_sel_prod")
        selected_product = prod_map[sel_prod_str]

    c3, c4, c5 = st.columns(3)
    with c3:
        order_qty = st.number_input("Order Quantity (Units)", min_value=1, value=50, step=5, key="po_order_qty")
    with c4:
        unit_price = st.number_input("Agreed Unit Price (₹)", min_value=0.0, value=float(selected_product.unit_cost), step=5.0, key="po_unit_price")
    with c5:
        total_val = order_qty * unit_price
        st.markdown(f"<div style='font-size:12px; color:var(--muted); margin-top:6px;'>TOTAL ORDER VALUE</div><div style='font-size:24px; font-weight:800; color:#00D4FF;'>₹{total_val:,.2f}</div>", unsafe_allow_html=True)

    po_notes = st.text_input("Optional Delivery Note:", placeholder="e.g. Urgent replenishment - please deliver by tomorrow", key="po_notes_input")

    # Generate Draft
    biz = next((business for business in database.list_businesses(user_id) if business.id == business_id), None)
    biz_name = biz.name if biz else "My Business Store"
    draft = comm_svc.generate_order_draft(
        business_name=biz_name,
        supplier=selected_supplier,
        product_name=selected_product.name,
        sku=selected_product.sku,
        quantity=int(order_qty),
        unit_price=float(unit_price),
        total_cost=float(total_val),
        notes=po_notes.strip() if po_notes else None,
    )

    st.markdown("#### 📝 Review Order Draft Message")
    st.text_area("Message Body (Editable before dispatch):", value=draft.formatted_body, height=180, key="po_edit_body")

    # Dispatch Channels
    st.markdown("#### 🚀 Select Dispatch Channel:")
    col_d1, col_d2, col_d3 = st.columns(3)

    with col_d1:
        if selected_supplier.phone:
            wa_url = comm_svc.get_whatsapp_url(selected_supplier.phone, draft.formatted_body)
            st.link_button("💬 Send via WhatsApp", wa_url, type="primary", width="stretch")
        else:
            st.caption("WhatsApp unavailable: this supplier has no phone number.")
        if st.button("✓ Mark WhatsApp PO Sent", key=f"mark_wa_{selected_supplier.id}", width="stretch"):
            comm_svc.record_communication(
                business_id=business_id,
                user_id=user_id,
                supplier_id=selected_supplier.id,
                comm_type=CommType.WHATSAPP,
                body=draft.formatted_body,
                subject=draft.subject,
                order_reference=draft.order_id,
                recipient=selected_supplier.phone,
                status=CommStatus.SENT,
            )
            st.success(f"✓ Recorded WhatsApp PO {draft.order_id} in communication history!")

    with col_d2:
        if st.button("✉️ Dispatch via Email", key=f"send_email_{selected_supplier.id}", type="secondary", width="stretch"):
            if not selected_supplier.email:
                st.error("This supplier does not have an email address configured.")
            else:
                ok, msg = comm_svc.send_email_order(
                    draft,
                    selected_supplier.email,
                    user_id=user_id,
                    business_id=business_id,
                    supplier_id=selected_supplier.id,
                )
                if ok:
                    st.success(f"✓ {msg}")
                else:
                    st.error(msg)

    with col_d3:
        if selected_supplier.phone:
            tel_url = comm_svc.get_phone_call_url(selected_supplier.phone)
            st.link_button(f"📞 Call {selected_supplier.phone}", tel_url, width="stretch")
            st.caption("ℹ️ Clicking will launch your device's native telephone dialer.")
        else:
            st.caption("Calling unavailable: this supplier has no phone number.")


def _render_communication_history(database: Database, business_id: str, user_id: str | None):
    """Render audit history of all supplier interactions."""
    comms = database.list_supplier_communications(business_id=business_id, user_id=user_id)

    if not comms:
        st.info("ℹ️ No supplier communications recorded yet. Dispatch a purchase order to start logging history.")
        return

    st.markdown(f"**📜 Communication Audit Ledger ({len(comms)} Records):**")

    for c in comms[:20]:
        badge_color = "#22C55E" if c.comm_type == "WHATSAPP" else ("#00D4FF" if c.comm_type == "EMAIL" else "#F59E0B")
        icon = "💬" if c.comm_type == "WHATSAPP" else ("✉️" if c.comm_type == "EMAIL" else "📞")

        _h(
            f"""
            <div class="agent-card" style="border-left: 3px solid {badge_color}; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-size: 13px; font-weight: 800; color: {badge_color};">
                        {icon} {c.comm_type} • Status: {c.status}
                    </div>
                    <div style="font-size: 11px; color: var(--muted);">
                        🕒 {c.created_at}
                    </div>
                </div>
                <div style="font-size: 14px; font-weight: 700; color: #FFFFFF; margin-top: 4px;">
                    Order Reference: <code>{c.order_reference or 'General Query'}</code>
                </div>
                <div style="font-size: 13px; color: var(--muted); margin-top: 4px; white-space: pre-wrap; background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: 8px;">
{c.body}
                </div>
            </div>
            """
        )
