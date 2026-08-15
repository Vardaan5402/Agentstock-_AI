import os
import streamlit as st
from uuid import uuid4
from database.database import Database
from models.business import Business
from models.inventory import Product
from models.supplier import Supplier, SupplierProduct
from ui.components import render_section_header

def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())

def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)

def render_settings_view(database: Database):
    """Render Catalog & Settings management view."""
    _h(
        """
        <div style="margin-bottom: 20px;">
            <h1 style="font-size: 30px; font-weight: 800; letter-spacing: -0.03em; margin: 0; color: #FFFFFF;">
                ⚙️ Catalog & Supplier Directory
            </h1>
            <div style="font-size: 14px; color: var(--muted); margin-top: 4px;">
                Manage business records, SKU catalog items, and supplier commercial terms for automated replenishment.
            </div>
        </div>
        """
    )

    render_section_header("Create Persistent Catalog Records", "New records created here are saved to SQLite for Decision Workbench selection", "➕")

    businesses = database.list_businesses()
    
    c_b, c_p = st.columns(2)
    
    with c_b:
        st.markdown("### Create New Business")
        with st.form("set_create_business_form"):
            b_name = st.text_input("Business Name", value="Organic Supermarket IN")
            b_country = st.text_input("Country", value="IN")
            b_curr = st.text_input("Currency", value="INR")
            b_ind = st.text_input("Industry", value="Retail Grocery")
            b_bud = st.number_input("Inventory Budget (₹)", min_value=0.0, value=10000.0)
            
            if st.form_submit_button("Save Business Record", type="primary"):
                try:
                    database.create_business(Business(
                        id=uuid4().hex, name=b_name, country=b_country, currency=b_curr,
                        industry=b_ind, inventory_budget=b_bud
                    ))
                    st.success("✓ New Business saved to SQLite!")
                    st.rerun()
                except ValueError as err:
                    st.error(str(err))

    with c_p:
        st.markdown("### Create New Product SKU")
        with st.form("set_create_product_form"):
            b_options = {b.name: b.id for b in businesses}
            if not b_options:
                st.warning("Create a Business first.")
                st.form_submit_button("Save Product SKU", disabled=True)
            else:
                selected_b_name = st.selectbox("Assign to Business", list(b_options.keys()))
                p_sku = st.text_input("SKU Code", value="RICE-5KG")
                p_name = st.text_input("Product Name", value="Basmati Rice 5kg Bag")
                p_stock = st.number_input("Current Stock (units)", min_value=0, value=25)
                p_cost = st.number_input("Unit Cost (₹)", min_value=0.0, value=350.0)
                p_demand = st.number_input("Daily Demand (units/day)", min_value=0.0, value=4.0)
                p_safety = st.number_input("Safety Stock (units)", min_value=0, value=10)

                if st.form_submit_button("Save Product SKU", type="primary"):
                    try:
                        database.create_product(Product(
                            id=uuid4().hex, business_id=b_options[selected_b_name],
                            sku=p_sku, name=p_name, current_stock=p_stock,
                            unit_cost=p_cost, daily_demand=p_demand, safety_stock=p_safety
                        ))
                        st.success("✓ New Product SKU saved to SQLite!")
                        st.rerun()
                    except Exception as err:
                        st.error(str(err))

    st.divider()
    st.markdown("### Create Supplier Commercial Terms")
    all_products = [p for b in businesses for p in database.list_products(b.id)]
    if not all_products:
        st.info("Create at least one product SKU to assign supplier commercial terms.")
    else:
        with st.form("set_create_supplier_form"):
            p_options = {f"{p.sku} — {p.name}": p for p in all_products}
            selected_p_str = st.selectbox("Target Product SKU", list(p_options.keys()))
            target_prod = p_options[selected_p_str]

            s_name = st.text_input("Supplier Name", value="National Grain Distributors")
            s_phone = st.text_input("Phone (WhatsApp)", value="+91 9569679741")
            s_lead = st.number_input("Lead Time (days)", min_value=0.0, value=2.0)
            s_rel = st.number_input("Reliability Score (0-1)", min_value=0.0, max_value=1.0, value=0.92)
            s_price = st.number_input("Unit Price (₹)", min_value=0.0, value=340.0)
            s_moq = st.number_input("MOQ (units)", min_value=1, value=5)

            if st.form_submit_button("Save Supplier Terms", type="primary"):
                try:
                    sup = Supplier(
                        id=uuid4().hex, business_id=target_prod.business_id,
                        name=s_name, phone=s_phone, lead_time_days=s_lead, reliability_score=s_rel
                    )
                    database.create_supplier_with_product(sup, SupplierProduct(
                        supplier_id=sup.id, product_id=target_prod.id,
                        unit_price=s_price, minimum_order_quantity=s_moq
                    ))
                    st.success("✓ Supplier commercial terms saved!")
                    st.rerun()
                except Exception as err:
                    st.error(str(err))

    st.divider()
    render_section_header("Active Supplier Directory & Direct Communication Desk", "Instant WhatsApp PO dispatch and phone calling for registered suppliers", "📞")

    from ui.components import render_supplier_communication_suite
    all_suppliers = [sup for b in businesses for sup in database.list_suppliers(b.id)]
    if not all_suppliers:
        render_supplier_communication_suite(
            supplier_name="FreshFarm Dairy Co",
            phone="+91 9569679741",
            email="dispatch@freshfarmdairy.com",
            sku="MILK-10L",
            product_name="Organic Whole Milk Crate (10L)",
            quantity=100,
            unit_price=55.0,
            total_cost="₹5,500.00",
        )
    else:
        for sup in all_suppliers[:3]:
            render_supplier_communication_suite(
                supplier_name=sup.name,
                phone=sup.phone if sup.phone else "+91 9569679741",
                email=f"sales@{sup.name.lower().replace(' ', '').replace('.', '')}.com",
                sku="SUPPLY-CATALOG",
                product_name="Catalog Supply Order",
                quantity=50,
                unit_price=120.0,
                total_cost="₹6,000.00",
            )
