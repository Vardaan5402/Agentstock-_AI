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
    user = st.session_state.get("authenticated_user")
    if not user:
        st.warning("Please sign in to manage your Business Profile.")
        return
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

    businesses = database.list_businesses(user.id)
    
    c_b, c_p = st.columns(2)
    
    with c_b:
        st.markdown("### Create New Business")
        with st.form("set_create_business_form"):
            b_name = st.text_input("Business Name")
            b_country = st.text_input("Country", value="IN")
            b_curr = st.text_input("Currency", value="INR")
            b_ind = st.text_input("Industry", value="Retail")
            b_bud = st.number_input("Inventory Budget (₹)", min_value=0.0, value=0.0)
            
            if st.form_submit_button("Save Business Record", type="primary"):
                try:
                    database.create_business(Business(
                        id=uuid4().hex, user_id=user.id, name=b_name, country=b_country, currency=b_curr,
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
                p_sku = st.text_input("SKU Code")
                p_name = st.text_input("Product Name")
                p_stock = st.number_input("Current Stock (units)", min_value=0, value=0)
                p_cost = st.number_input("Unit Cost (₹)", min_value=0.0, value=0.0)
                p_demand = st.number_input("Daily Demand (units/day)", min_value=0.0, value=0.0)
                p_safety = st.number_input("Safety Stock (units)", min_value=0, value=0)

                if st.form_submit_button("Save Product SKU", type="primary"):
                    try:
                        database.create_product(Product(
                            id=uuid4().hex, business_id=b_options[selected_b_name], user_id=user.id,
                            sku=p_sku, name=p_name, current_stock=p_stock,
                            unit_cost=p_cost, daily_demand=p_demand, safety_stock=p_safety
                        ))
                        st.success("✓ New Product SKU saved to SQLite!")
                        st.rerun()
                    except Exception as err:
                        st.error(str(err))

    st.info("Manage suppliers and purchase orders in Supplier Directory & POs. New accounts start with an empty supplier directory.")
