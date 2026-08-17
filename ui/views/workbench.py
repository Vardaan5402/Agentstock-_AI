import os
import streamlit as st
from uuid import uuid4
from database.database import Database
from models.business import Business
from models.inventory import Product
from models.policy import Policy
from models.supplier import Supplier, SupplierProduct
from models.decision_workflow import DecisionWorkflowInput, DecisionWorkflowStatus
from core.decision_workflow import run_decision_workflow
from core.gemini_reasoner import GeminiStructuredReasoner
from core.decision_copilot import DecisionCopilot
from core.decision_context import derive_required_uncertainties
from core.decision_persistence import (
    approve_decision_review,
    reject_decision_review,
    save_decision_review,
)
from ui.components import (
    render_section_header,
    render_recommendation_hero,
    render_supplier_communication_suite,
    render_ai_pipeline_banner,
    render_kpi_card,
)
from ui.charts import create_simulation_timeline_chart, create_supplier_comparison_chart

def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())

def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)

def _supplier_inputs_card(prefix: str, defaults: tuple[str, float, int, float, float]):
    """Collect one supplier's commercial terms inside a styled card."""
    name, price, moq, lead_time, reliability = defaults
    with st.container():
        _h(
            f"""
            <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid var(--border); border-radius: 16px; padding: 16px; margin-bottom: 12px;">
                <div style="font-weight: 700; font-size: 15px; color: var(--primary-light); margin-bottom: 10px;">
                    🚚 Supplier {prefix} Commercial Terms
                </div>
            </div>
            """
        )
        c1, c2 = st.columns(2)
        s_name = c1.text_input("Supplier name", value=name, key=f"wb_s_name_{prefix}")
        s_price = c2.number_input("Unit price (₹)", min_value=0.0, value=price, key=f"wb_s_price_{prefix}")
        
        c3, c4, c5 = st.columns(3)
        s_moq = c3.number_input("MOQ (units)", min_value=1, value=moq, step=1, key=f"wb_s_moq_{prefix}")
        s_lead = c4.number_input("Lead time (days)", min_value=0.0, value=lead_time, key=f"wb_s_lead_{prefix}")
        s_rel = c5.number_input("Reliability (0–1)", min_value=0.0, max_value=1.0, value=reliability, step=0.05, key=f"wb_s_rel_{prefix}")
        
    return {
        "name": s_name,
        "unit_price": s_price,
        "minimum_order_quantity": s_moq,
        "lead_time_days": s_lead,
        "reliability_score": s_rel,
    }


def _build_input(values: dict, suppliers: list) -> DecisionWorkflowInput:
    """Build domain models from form values."""
    business = Business(
        id=str(values.get("business_id", "workbench-business")),
        name=str(values["business_name"]),
        country=str(values["country"]),
        currency=str(values["currency"]),
        industry=str(values["industry"]),
        inventory_budget=float(values["budget"]),
    )
    product = Product(
        id=str(values.get("product_id", "workbench-product")),
        business_id=business.id,
        sku=str(values["sku"]),
        name=str(values["product_name"]),
        current_stock=int(values["current_stock"]),
        unit_cost=float(values["unit_cost"]),
        daily_demand=float(values["daily_demand"]),
        safety_stock=int(values["safety_stock"]),
    )
    policy = Policy(
        id="workbench-review-policy",
        business_id=business.id,
        max_auto_purchase=0.0,
        require_approval=True,
        allowed_auto_actions=[],
    )
    supplier_models = []
    supplier_products = []
    for idx, s in enumerate(suppliers, start=1):
        s_id = f"workbench-supplier-{idx}"
        supplier_models.append(
            Supplier(
                id=s_id,
                business_id=business.id,
                name=str(s["name"]),
                lead_time_days=float(s["lead_time_days"]),
                reliability_score=float(s["reliability_score"]),
            )
        )
        supplier_products.append(
            SupplierProduct(
                supplier_id=s_id,
                product_id=product.id,
                unit_price=float(s["unit_price"]),
                minimum_order_quantity=int(s["minimum_order_quantity"]),
            )
        )
    return DecisionWorkflowInput(
        business=business,
        product=product,
        policy=policy,
        suppliers=tuple(supplier_models),
        supplier_products=tuple(supplier_products),
        available_budget=float(values["budget"]),
        simulation_days=int(values["simulation_days"]),
    )


def render_workbench_view(database: Database):
    """Render the main Decision Workbench view."""
    _h(
        """
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
            <div>
                <h1 style="font-size: 30px; font-weight: 800; letter-spacing: -0.03em; margin: 0; color: #FFFFFF;">
                    ⚡ AI Decision Workbench
                </h1>
                <div style="font-size: 14px; color: var(--muted); margin-top: 4px;">
                    Simulate inventory scenarios, evaluate supplier options, and generate verified Gemini reasoning.
                </div>
            </div>
        </div>
        """
    )

    from core.billing.subscription_service import SubscriptionService
    from ui.components import render_subscription_locked_card
    user = st.session_state.get("authenticated_user")
    user_id = user.id if user else None
    sub_svc = SubscriptionService(database)
    is_subscribed = sub_svc.is_subscription_active(user_id) if user_id else False
    is_admin = getattr(user, "role", "") == "ADMIN"

    if not is_subscribed and not is_admin:
        render_subscription_locked_card("AI Decision Workbench & Simulation Engine")
        return

    render_ai_pipeline_banner(current_step=4 if "decision_workflow_result" in st.session_state else 2)

    # Workbench Configuration Form
    with st.expander("📝 Configure Decision Input Parameters", expanded=st.session_state.get("decision_workflow_result") is None):
        with st.form("decision_workbench_form_modern"):
            render_section_header("Step 1 & 2: Business, SKU & Inventory Inputs", "Specify current stock level and demand burn rate", "📊")
            
            b1, b2, b3 = st.columns(3)
            business_name = b1.text_input("Business name", value="Metro Organic Grocers")
            country = b2.text_input("Country", value="IN")
            currency = b3.text_input("Currency", value="INR")

            b4, b5, b6 = st.columns(3)
            industry = b4.text_input("Industry", value="Retail grocery")
            sku = b5.text_input("Product SKU", value="MILK-10L")
            product_name = b6.text_input("Product name", value="Organic whole milk (10L crate)")

            i1, i2, i3, i4, i5, i6 = st.columns(6)
            current_stock = i1.number_input("Stock", min_value=0, value=12, step=1)
            daily_demand = i2.number_input("Demand/day", min_value=0.0, value=6.0)
            safety_stock = i3.number_input("Safety stock", min_value=0, value=5, step=1)
            unit_cost = i4.number_input("Unit cost", min_value=0.0, value=100.0)
            budget = i5.number_input("Budget (₹)", min_value=0.0, value=5000.0)
            simulation_days = i6.number_input("Horizon (days)", min_value=1, value=14, step=1)

            render_section_header("Step 3: Supplier Commercial Terms", "Compare 3 supplier options with varying price, lead time and MOQ", "🚚")

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                sup_a = _supplier_inputs_card("A", ("Rapid Dairy Logistics", 120.0, 1, 1.0, 0.90))
            with col_b:
                sup_b = _supplier_inputs_card("B", ("Value Dairy Co.", 85.0, 1, 5.0, 0.80))
            with col_c:
                sup_c = _supplier_inputs_card("C", ("Bulk Dairy Partners", 110.0, 50, 2.0, 0.95))

            submitted = st.form_submit_button("⚡ Generate Decision Review", type="primary")
            if submitted:
                try:
                    workflow_input = _build_input(
                        {
                            "business_id": "workbench-business",
                            "product_id": "workbench-product",
                            "business_name": business_name,
                            "country": country,
                            "currency": currency,
                            "industry": industry,
                            "sku": sku,
                            "product_name": product_name,
                            "current_stock": current_stock,
                            "daily_demand": daily_demand,
                            "safety_stock": safety_stock,
                            "unit_cost": unit_cost,
                            "budget": budget,
                            "simulation_days": simulation_days,
                        },
                        [sup_a, sup_b, sup_c],
                    )
                    reasoner = GeminiStructuredReasoner() if os.environ.get("GEMINI_API_KEY") else None
                    st.session_state["decision_workflow_result"] = run_decision_workflow(workflow_input, reasoner)
                    st.session_state["what_if_comparison"] = None
                    st.session_state["what_if_scenario"] = None
                    st.session_state["saved_decision_snapshot_id"] = None
                    st.rerun()
                except ValueError as err:
                    st.error(f"Input Validation Error: {err}")

    # Display Results if available
    result = st.session_state.get("decision_workflow_result")
    if result is None:
        st.info("💡 Configure parameters above and click **'Generate Decision Review'** to run deterministic forecasting and AI supplier evaluation.")
        return

    # Status Banner
    if result.status is DecisionWorkflowStatus.READY_FOR_REVIEW:
        st.success(f"✓ **Status**: {result.status_detail}")
    elif result.status is DecisionWorkflowStatus.REASONING_UNAVAILABLE:
        st.info(f"ℹ️ **Status**: {result.status_detail}")
    else:
        st.warning(f"⚠️ **Status**: {result.status_detail}")

    # Snapshot ID bar
    _h(
        f"""
        <div style="background: var(--surface-2); border: 1px solid var(--border); border-radius: 12px; padding: 10px 16px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 13px; color: var(--muted);">Authoritative Immutable Snapshot ID:</span>
            <code style="font-family: var(--font-mono); color: var(--accent); font-size: 13px;">{result.facts.snapshot_id}</code>
        </div>
        """
    )

    # 1. AI HERO RECOMMENDATION CARD
    render_section_header("AI Recommendation Hero", "Fact-bounded decision proposal from Gemini 3.6 Flash", "✨")

    # Find recommended option details
    rec_supplier_name = "No supplier selected"
    rec_supplier_id = None
    rec_cost = "—"
    rec_coverage = "—"
    rec_lead = "—"
    rec_qty = "—"
    rec_unit_price = "—"
    rec_confidence = "HIGH"
    rec_risk = result.facts.inventory_risk.stockout_risk
    
    if result.proposal is not None:
        rec_confidence = result.proposal.confidence.value
        selected_id = result.proposal.selected_scenario_id
        if selected_id.startswith("PURCHASE_"):
            opt_id = selected_id.replace("PURCHASE_", "")
            opt = next((o for o in result.facts.purchase_options if o.option_id == opt_id), None)
            if opt:
                rec_supplier_id = opt.supplier_id
                sup = next((s for s in result.baseline.suppliers if s.id == opt.supplier_id), None)
                rec_supplier_name = sup.name if sup else opt.supplier_id
                rec_cost = f"₹{opt.total_cost:,.2f}"
                rec_unit_price = f"{opt.unit_price:.2f}"
                rec_coverage = f"{result.facts.inventory_risk.runway_days:.1f} Days" if result.facts.inventory_risk.runway_days else "0 Days"
                rec_lead = f"{opt.supplier_lead_time_days:.1f} Days"
                rec_qty = f"{opt.purchase_quantity} Units"

    render_recommendation_hero(
        supplier_name=rec_supplier_name,
        confidence=rec_confidence,
        stockout_risk=rec_risk,
        estimated_cost=rec_cost,
        coverage_days=rec_coverage,
        lead_time_days=rec_lead,
        order_quantity=rec_qty,
        budget_feasible=True,
        lead_time_feasible=True,
        policy_compliant=result.policy_validation.compliant if result.policy_validation else True,
        evidence_verified=result.reference_validation.valid if result.reference_validation else True,
    )

    # 1B. INSTANT SUPPLIER DISPATCH & COMMUNICATION SUITE
    selected_supplier = database.get_supplier(rec_supplier_id, user.id) if rec_supplier_id and user else None
    if selected_supplier:
        render_supplier_communication_suite(
            supplier_name=selected_supplier.company_name or selected_supplier.name,
            phone=selected_supplier.phone,
            email=selected_supplier.email,
            sku=result.baseline.product.sku,
            product_name=result.baseline.product.name,
            quantity=rec_qty,
            unit_price=rec_unit_price,
            total_cost=rec_cost,
        )
    else:
        st.info("No owned supplier is selected for this recommendation. Add or select a supplier in Supplier Directory & POs before dispatching a PO.")

    # 2. DECISION EXPLANATION & EVIDENCE VERIFICATION
    render_section_header("Why This Decision? (Fact-Bounded Explanation)", "Grounded qualitative reasoning & verified fact pointers", "🔍")

    if result.proposal is None:
        st.info("Gemini reasoning was not requested or is currently offline. Review the deterministic evidence below.")
    else:
        _h(
            f"""
            <div class="agent-card" style="border-left: 4px solid var(--accent);">
                <div style="font-size: 15px; font-weight: 700; color: #FFFFFF; margin-bottom: 8px;">
                    🤖 Qualitative Reasoning from Gemini
                </div>
                <div style="font-size: 14px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 16px;">
                    {result.proposal.qualitative_reasoning}
                </div>
                <div style="font-size: 13px; font-weight: 600; color: var(--muted); margin-bottom: 8px;">
                    Trade-off Explanation:
                </div>
                <div style="font-size: 14px; color: #CBD5E1; line-height: 1.5; background: rgba(0,0,0,0.2); padding: 12px; border-radius: 10px;">
                    {result.proposal.trade_off_explanation}
                </div>
            </div>
            """
        )

        with st.expander("🔍 View Verified Reasoning Claims & Fact References", expanded=True):
            for idx, claim in enumerate(result.proposal.reasoning_claims, start=1):
                st.markdown(f"**Claim {idx}**: {claim.claim}")
                if claim.fact_references:
                    st.caption("Verified Fact References:")
                    for ref in claim.fact_references:
                        st.code(ref, language=None)
                if claim.compared_scenario_ids:
                    st.caption(f"Compared Scenarios: {', '.join(claim.compared_scenario_ids)}")
                st.divider()

    # 3. SUPPLIER COMPARISON CARDS & CHART
    render_section_header("Supplier Options & Deterministic Feasibility", "Side-by-side commercial terms and stockout risk analysis", "📊")

    s1, s2 = st.columns([2, 1])
    with s1:
        # Render visual supplier cards
        supplier_risk = {item.supplier_id: item.inventory_risk for item in result.baseline_outcome.supplier_outcomes}
        for opt in result.facts.purchase_options:
            sup = next((s for s in result.baseline.suppliers if s.id == opt.supplier_id), None)
            sup_name = sup.name if sup else opt.supplier_id
            is_rec = (result.proposal and result.proposal.selected_scenario_id == f"PURCHASE_{opt.option_id}")
            
            border = "border: 2px solid var(--success);" if is_rec else "border: 1px solid var(--border);"
            rec_tag = '<span class="badge badge-success" style="float: right; margin-left: 8px;">★ RECOMMENDED</span>' if is_rec else ''
            
            if opt.feasible:
                status_badge = '<span style="color: #22C55E; font-size: 11px; font-weight: 700; background: rgba(34, 197, 94, 0.12); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(34, 197, 94, 0.3);">✓ Feasible</span>'
            else:
                status_badge = '<span style="color: #EF4444; font-size: 11px; font-weight: 700; background: rgba(239, 68, 68, 0.12); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(239, 68, 68, 0.3);">✕ Infeasible</span>'
            
            reason_text = opt.reason or ("Option is feasible" if opt.feasible else "Constraint breached")

            _h(
                f"""
                <div class="agent-card" style="{border}; margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="font-size: 17px; font-weight: 800; color: #FFFFFF;">
                            {sup_name} {status_badge}
                        </div>
                        <div>{rec_tag}</div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 10px; font-size: 13px;">
                        <div><span style="color:var(--muted);">Unit Price:</span><br/><strong style="color:#FFF;">₹{opt.unit_price}</strong></div>
                        <div><span style="color:var(--muted);">Lead Time:</span><br/><strong style="color:#FFF;">{opt.supplier_lead_time_days} days</strong></div>
                        <div><span style="color:var(--muted);">Total Cost:</span><br/><strong style="color:#FFF;">₹{opt.total_cost:,.2f}</strong></div>
                        <div><span style="color:var(--muted);">Reliability:</span><br/><strong style="color:#FFF;">{opt.supplier_reliability*100:.0f}%</strong></div>
                    </div>
                    <div style="margin-top: 8px; font-size: 12px; color: var(--muted); border-top: 1px solid rgba(255, 255, 255, 0.05); padding-top: 6px;">
                        <strong style="color: var(--text-secondary);">Constraint Check:</strong> {reason_text}
                    </div>
                </div>
                """
            )
            
    sup_names_map = {s.id: s.name for s in result.baseline.suppliers}
    with s2:
        chart_sup = create_supplier_comparison_chart(result.facts.purchase_options, supplier_names=sup_names_map)
        if chart_sup:
            st.plotly_chart(chart_sup, width="stretch")

    # 4. INTERACTIVE SIMULATION TIMELINE
    render_section_header("Simulation Evidence & Inventory Trajectory", "14-day forward simulation across all purchase scenarios", "📈")

    sim_fig = create_simulation_timeline_chart(
        result.facts.simulations,
        result.facts.inventory_risk.current_stock,
        result.facts.inventory_risk.daily_demand,
        result.facts.inventory_risk.safety_stock,
        result.baseline.simulation_days,
        supplier_names=sup_names_map,
    )
    st.plotly_chart(sim_fig, width="stretch")

    # 5. ENTERPRISE HUMAN DECISION REVIEW WORKFLOW
    render_section_header("Human Approval Workflow", "Enterprise sign-off for purchase order release", "👤")

    _h(
        """
        <div class="agent-card" style="border-top: 4px solid var(--primary-light);">
            <div style="font-size: 16px; font-weight: 700; color: #FFFFFF; margin-bottom: 6px;">
                HUMAN DECISION REQUIRED
            </div>
            <div style="font-size: 13px; color: var(--muted); margin-bottom: 16px;">
                Review the AI recommendation above. Purchase actions require explicit human authorization and generate a permanent audit trail.
            </div>
        </div>
        """
    )

    c_rev1, c_rev2 = st.columns(2)
    reviewer_name = c_rev1.text_input("Reviewer Name", value="CSO / Supply Chain Manager", key="wb_reviewer_name")
    review_comment = c_rev2.text_area("Reviewer Comment", placeholder="Provide rationale for approval or rejection...", key="wb_reviewer_comment")

    btn_app, btn_rej = st.columns(2)
    with btn_app:
        if st.button("✅ Approve Recommendation", type="primary", key="wb_btn_approve"):
            try:
                approve_decision_review(database, result.facts.snapshot_id, reviewer=reviewer_name)
                st.success(f"✓ Decision review `{result.facts.snapshot_id[:12]}` APPROVED by {reviewer_name}!")
            except ValueError as e:
                st.error(str(e))
    with btn_rej:
        if st.button("❌ Reject Recommendation", type="secondary", key="wb_btn_reject"):
            try:
                reject_decision_review(database, result.facts.snapshot_id, reviewer=reviewer_name, reason=review_comment)
                st.warning(f"✕ Decision review `{result.facts.snapshot_id[:12]}` REJECTED by {reviewer_name}.")
            except ValueError as e:
                st.error(str(e))

    # 6. GEMINI DECISION COPILOT ASSISTANT
    render_section_header("🤖 AgentStock Decision Copilot", "Ask questions grounded strictly in the authoritative evidence", "💬")

    gemini_online = bool(os.environ.get("GEMINI_API_KEY"))
    if gemini_online:
        copilot_q = st.text_input(
            "Ask Copilot a Question",
            value=st.session_state.get("wb_copilot_q", ""),
            placeholder="Why is Rapid Dairy Logistics recommended over Value Dairy Co?",
            key="wb_copilot_q_input"
        )
        
        c_ask, c_sugg1, c_sugg2 = st.columns([1, 1, 1])
        with c_ask:
            ask_clicked = st.button("Ask Copilot ✨", type="secondary", key="wb_btn_copilot")
        with c_sugg1:
            if st.button("Why this supplier?", key="sugg_1"):
                copilot_q = "Why is this supplier considered the best option?"
                st.session_state["wb_copilot_q"] = copilot_q
                ask_clicked = True
        with c_sugg2:
            if st.button("What are the risks?", key="sugg_2"):
                copilot_q = "What stockout and lead time risks exist in this snapshot?"
                st.session_state["wb_copilot_q"] = copilot_q
                ask_clicked = True

        if ask_clicked and copilot_q.strip():
            with st.spinner("Copilot is analyzing DecisionFacts evidence..."):
                try:
                    c_reasoner = GeminiStructuredReasoner()
                    copilot = DecisionCopilot(c_reasoner)
                    ans = copilot.ask(result, copilot_q)
                    
                    _h(
                        f"""
                        <div class="chat-bubble-ai">
                            <strong style="color: var(--primary-light);">🤖 AgentStock Copilot:</strong><br/>
                            {ans}
                        </div>
                        """
                    )
                except Exception as err:
                    err_msg = str(err)
                    if "RESOURCE_EXHAUSTED" in err_msg or "credits" in err_msg:
                        st.warning("⚠️ Gemini Copilot is temporarily unavailable due to API rate limits. The deterministic decision engine remains fully operational.")
                    else:
                        st.error(f"Copilot Response Error: {err}")
    else:
        st.info("ℹ️ Gemini Copilot is offline. Add GEMINI_API_KEY to environment variables to enable interactive AI QA.")

    # Save & Export Controls
    st.divider()
    e1, e2 = st.columns(2)
    with e1:
        if st.button("💾 Save Decision Review to Database", type="primary", key="wb_save_review"):
            saved = save_decision_review(database, result)
            st.session_state["saved_decision_snapshot_id"] = saved.snapshot_id
            st.success(f"✓ Immutable decision review saved: `{saved.snapshot_id}`")
    with e2:
        st.download_button(
            "📥 Download DecisionFacts JSON",
            data=result.facts.canonical_json(),
            file_name=f"agentstock-facts-{result.facts.snapshot_id[:10]}.json",
            mime="application/json",
            key="wb_download_facts"
        )
