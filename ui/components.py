import streamlit as st

def _clean_html(html_str: str) -> str:
    """Strip leading whitespace from every line so Streamlit markdown never triggers code blocks."""
    return "\n".join(line.lstrip() for line in html_str.splitlines())

def _h(html_str: str):
    """Render HTML cleanly without Markdown code block artifacts."""
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


def render_brand_header():
    """Render sidebar brand logo header."""
    _h(
        """
        <div class="brand-header">
            <div class="brand-icon">⚡</div>
            <div>
                <div class="brand-name">AgentStock AI</div>
                <div class="brand-tag">Supply Chain Intelligence</div>
            </div>
        </div>
        """
    )


def render_system_status_bar(gemini_available: bool = True):
    """Render a top status bar displaying engine connectivity and system state."""
    status_text = "GEMINI 3.6 FLASH ONLINE — Fact-Bounded AI Operational" if gemini_available else "STANDALONE MODE — Deterministic Engine Active (Set GEMINI_API_KEY for LLM Reasoning)"
    status_class = "badge-success" if gemini_available else "badge-warning"
    _h(
        f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: rgba(13, 20, 34, 0.8); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 20px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div class="status-dot" style="background-color: {'#22C55E' if gemini_available else '#F59E0B'};"></div>
                <span style="font-size: 13px; font-weight: 600; color: #FFFFFF;">{status_text}</span>
            </div>
            <span class="badge {status_class}" style="font-size: 11px;">
                {'AI ACTIVE' if gemini_available else 'LOCAL STANDALONE'}
            </span>
        </div>
        """
    )


def render_kpi_card(title: str, value: str, icon: str = "📈", subtitle: str = None, color: str = None):
    """Render a modern glassmorphic metric card string."""
    color_style = f"color: {color};" if color else "color: #FFFFFF;"
    sub_html = f'<div class="metric-sub">{subtitle}</div>' if subtitle else ""
    return _clean_html(
        f"""
        <div class="metric-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <span class="metric-label">{title}</span>
                <span style="font-size: 18px;">{icon}</span>
            </div>
            <div class="metric-value" style="{color_style}">{value}</div>
            {sub_html}
        </div>
        """
    )


def render_ai_pipeline_banner(current_step: int = 1):
    """Render the 5-step AI decision workflow banner."""
    steps = [
        ("Fact Engine", "Deterministic Simulation", "⚙️"),
        ("Feasibility Check", "Policy & Constraint Audit", "🛡️"),
        ("Gemini AI", "Structured Reasoning", "✨"),
        ("Fact Verification", "Reference Claim Check", "🔍"),
        ("Human Governance", "Immutable Sign-Off", "👤"),
    ]

    html_parts = ['<div class="pipeline-container">']
    for idx, (label, sub, icon) in enumerate(steps, start=1):
        step_class = "pipeline-step"
        if idx == current_step:
            step_class += " active"
        elif idx < current_step:
            step_class += " success"

        html_parts.append(
            f"""
            <div class="{step_class}">
                <div class="pipeline-icon">{icon}</div>
                <div class="pipeline-label">Step {idx}: {label}</div>
                <div class="pipeline-sub">{sub}</div>
            </div>
            """
        )
        if idx < len(steps):
            html_parts.append('<div class="pipeline-arrow">➔</div>')
    html_parts.append("</div>")

    _h("\n".join(html_parts))


def render_recommendation_hero(
    supplier_name: str,
    confidence: str,
    stockout_risk: str,
    estimated_cost: str,
    coverage_days: str,
    lead_time_days: str,
    order_quantity: str,
    budget_feasible: bool = True,
    lead_time_feasible: bool = True,
    policy_compliant: bool = True,
    evidence_verified: bool = True,
):
    """Render the main hero card showing the AI decision recommendation."""
    badge_class = "badge-success" if confidence == "HIGH" else ("badge-warning" if confidence == "MEDIUM" else "badge-danger")
    risk_class = "badge-danger" if stockout_risk == "HIGH" else ("badge-warning" if stockout_risk == "MEDIUM" else "badge-success")

    _h(
        f"""
        <div class="hero-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
                <div>
                    <div class="hero-badge">
                        ✨ FACT-BOUNDED AI RECOMMENDATION
                    </div>
                    <div class="hero-title">Optimal Replenishment Action:</div>
                    <div class="hero-supplier-name">Order from {supplier_name}</div>
                </div>
                <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
                    <span class="badge {badge_class}" style="font-size: 13px; padding: 6px 16px;">
                        CONFIDENCE: {confidence}
                    </span>
                    <span class="badge {risk_class}" style="font-size: 12px;">
                        STOCKOUT RISK: {stockout_risk}
                    </span>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-top: 24px; margin-bottom: 24px;">
                {render_kpi_card("ESTIMATED COST", estimated_cost, "💰")}
                {render_kpi_card("REPLENISHMENT COVERAGE", coverage_days, "⏳")}
                {render_kpi_card("SUPPLIER LEAD TIME", lead_time_days, "🚚")}
                {render_kpi_card("OPTIMAL ORDER QTY", order_quantity, "📦")}
            </div>

            <div style="display: flex; flex-wrap: wrap; gap: 10px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.08);">
                <span class="badge {'badge-success' if budget_feasible else 'badge-danger'}">
                    {'✓' if budget_feasible else '✕'} Budget Feasible
                </span>
                <span class="badge {'badge-success' if lead_time_feasible else 'badge-danger'}">
                    {'✓' if lead_time_feasible else '✕'} Lead Time Feasible
                </span>
                <span class="badge {'badge-success' if policy_compliant else 'badge-warning'}">
                    {'✓' if policy_compliant else '⚠'} Policy Compliant
                </span>
                <span class="badge {'badge-success' if evidence_verified else 'badge-danger'}">
                    {'✓' if evidence_verified else '✕'} Evidence Verified
                </span>
            </div>
        </div>
        """
    )


def render_supplier_communication_suite(
    supplier_name: str,
    phone: str | None,
    email: str | None,
    sku: str,
    product_name: str,
    quantity: str | int,
    unit_price: str | float,
    total_cost: str,
):
    """Render interactive Calling, WhatsApp, SMS/Email PO dispatch suite for chosen supplier."""
    import urllib.parse

    clean_phone = "".join(c for c in str(phone or "") if c.isdigit() or c == "+")

    wa_msg = (
        f"Hello {supplier_name} Sales Desk,\n\n"
        f"AgentStock AI has approved a Purchase Order for dispatch:\n"
        f"• SKU: {sku} ({product_name})\n"
        f"• Order Quantity: {quantity} units\n"
        f"• Agreed Unit Price: ₹{unit_price}\n"
        f"• Total PO Value: {total_cost}\n\n"
        f"Please confirm PO receipt and estimated delivery date."
    )
    encoded_wa = urllib.parse.quote(wa_msg)
    wa_url = f"https://wa.me/{clean_phone.replace('+', '')}?text={encoded_wa}" if clean_phone else None

    email_sub = urllib.parse.quote(f"[AgentStock PO Dispatch] {sku} - {quantity} Units")
    email_body = urllib.parse.quote(wa_msg)
    mailto_url = f"mailto:{email}?subject={email_sub}&body={email_body}" if email else None
    tel_url = f"tel:{clean_phone}" if clean_phone else None

    _h(
        f"""
        <div class="agent-card" style="border: 1px solid var(--primary-light); background: linear-gradient(135deg, rgba(109, 93, 252, 0.12), rgba(13, 20, 34, 0.98));">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div style="font-size: 16px; font-weight: 800; color: #FFFFFF;">
                    📞 Instant Supplier Communication & Dispatch Suite
                </div>
                <span class="badge badge-success">● Direct Dispatch Active</span>
            </div>
            <div style="font-size: 13px; color: var(--muted); margin-bottom: 16px;">
                Dispatch PO directly to <strong>{supplier_name}</strong> via WhatsApp, phone dialer, or official email with 1 click:
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 16px;">
                {f'''<a href="{wa_url}" target="_blank" style="text-decoration: none;">
                    <div style="background: linear-gradient(135deg, #25D366, #128C7E); color: #FFF; font-weight: 700; padding: 12px 16px; border-radius: 12px; text-align: center; font-size: 14px; box-shadow: 0 4px 15px rgba(37, 211, 102, 0.3);">
                        💬 Dispatch via WhatsApp
                    </div>
                </a>''' if wa_url else '<div style="color: var(--muted); font-size: 13px;">WhatsApp unavailable: no supplier phone.</div>'}
                {f'''<a href="{tel_url}" target="_blank" style="text-decoration: none;">
                    <div style="background: linear-gradient(135deg, #3B82F6, #1D4ED8); color: #FFF; font-weight: 700; padding: 12px 16px; border-radius: 12px; text-align: center; font-size: 14px; box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);">
                        📞 Call Sales ({clean_phone})
                    </div>
                </a>''' if tel_url else '<div style="color: var(--muted); font-size: 13px;">Calling unavailable: no supplier phone.</div>'}
                {f'''<a href="{mailto_url}" target="_blank" style="text-decoration: none;">
                    <div style="background: rgba(255, 255, 255, 0.08); border: 1px solid var(--border-light); color: #FFF; font-weight: 700; padding: 12px 16px; border-radius: 12px; text-align: center; font-size: 14px;">
                        ✉️ Email Official PO
                    </div>
                </a>''' if mailto_url else '<div style="color: var(--muted); font-size: 13px;">Email unavailable: no supplier email.</div>'}
            </div>

            <details style="margin-top: 10px; font-size: 13px; color: var(--text-secondary);">
                <summary style="cursor: pointer; font-weight: 600; color: var(--primary-light);">📋 View & Copy Pre-Formatted PO Payload</summary>
                <div style="background: rgba(0,0,0,0.3); border: 1px solid var(--border); border-radius: 10px; padding: 12px; margin-top: 8px; font-family: var(--font-mono); font-size: 12px; white-space: pre-wrap; color: #E2E8F0;">
{wa_msg}
                </div>
            </details>
        </div>
        """
    )


def render_section_header(title: str, subtitle: str = None, icon: str = None):
    """Render a styled section header with title and subtitle."""
    icon_html = f'<span style="color: var(--primary-light); margin-right: 8px;">{icon}</span>' if icon else ""
    sub_html = f'<div style="color: var(--muted); font-size: 14px; margin-top: 4px; margin-bottom: 20px;">{subtitle}</div>' if subtitle else ""

    _h(
        f"""
        <div style="margin-top: 24px; margin-bottom: 12px;">
            <h2 style="font-size: 22px; font-weight: 700; margin: 0; display: flex; align-items: center; color: #FFFFFF;">
                {icon_html}{title}
            </h2>
            {sub_html}
        </div>
        """
    )


def render_what_if_delta_card(
    metric_name: str,
    baseline_val: str,
    what_if_val: str,
    delta_str: str,
    status: str = "neutral",  # "improved", "worsened", "neutral"
):
    """Render a BASELINE vs. WHAT-IF delta card string."""
    card_class = f"delta-card delta-{status}"
    badge_class = "badge-success" if status == "improved" else ("badge-danger" if status == "worsened" else "badge-info")

    return _clean_html(
        f"""
        <div class="{card_class}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <span style="font-weight: 700; font-size: 15px; color: #FFFFFF;">{metric_name}</span>
                <span class="badge {badge_class}">{delta_str}</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 14px;">
                <div style="color: var(--muted);">
                    Baseline: <strong style="color: var(--text-secondary);">{baseline_val}</strong>
                </div>
                <div style="font-size: 16px;">➔</div>
                <div style="color: var(--muted);">
                    What-If: <strong style="color: #FFFFFF;">{what_if_val}</strong>
                </div>
            </div>
        </div>
        """
    )


def render_pricing_card(
    title: str,
    price: str,
    period: str,
    description: str,
    features: list[str],
    is_popular: bool = False,
    button_text: str = "Get Started",
    key: str = "pricing_btn",
):
    """Render a single pricing card using native Streamlit container formatting."""
    with st.container(border=True):
        if is_popular:
            st.markdown(
                '<span style="background: linear-gradient(90deg, #6D5DFC, #00D4FF); color: #FFFFFF; font-size: 11px; font-weight: 800; padding: 4px 12px; border-radius: 999px; letter-spacing: 0.08em; text-transform: uppercase;">★ MOST POPULAR</span>',
                unsafe_allow_html=True
            )

        st.markdown(f"<h3 style='margin-top: 8px; margin-bottom: 4px; color: #FFFFFF; font-weight: 800;'>{title}</h3>", unsafe_allow_html=True)
        st.caption(description)
        st.markdown(f"<div style='margin-top: 12px; margin-bottom: 16px;'><span style='font-size: 32px; font-weight: 800; color: #FFFFFF;'>{price}</span> <span style='font-size: 13px; color: #94A3B8;'>{period}</span></div>", unsafe_allow_html=True)
        st.divider()

        for feat in features:
            st.markdown(f"<div style='font-size: 13px; color: #CBD5E1; margin-bottom: 8px;'><span style='color: #22C55E; font-weight: 700;'>✓</span> {feat}</div>", unsafe_allow_html=True)

        st.button(button_text, key=key, type="primary" if is_popular else "secondary", width="stretch")


def render_subscription_locked_card(feature_title: str = "This Feature"):
    """Render a clean, friendly subscription upgrade card for locked operational tools."""
    _h(
        f"""
        <div style="background: rgba(109, 93, 252, 0.08); border: 1.5px solid rgba(109, 93, 252, 0.35); border-radius: 16px; padding: 28px 24px; text-align: center; max-width: 680px; margin: 20px auto 30px auto;">
            <div style="font-size: 38px; margin-bottom: 10px;">🔒</div>
            <div style="font-size: 22px; font-weight: 800; color: #FFFFFF;">Subscription Required</div>
            <div style="font-size: 15px; font-weight: 600; color: #A5B4FC; margin-top: 4px;">Your workspace is ready.</div>
            <div style="font-size: 13.5px; color: #CBD5E1; line-height: 1.6; margin: 12px auto 20px auto; max-width: 540px;">
                Choose an active plan to activate <strong>{feature_title}</strong>, AI stock recognition, supplier workflows, purchase order dispatching, and automated business tools.
            </div>
        </div>
        """
    )
    c_btn1, c_btn2, c_btn3 = st.columns([1, 1.5, 1])
    with c_btn2:
        btn_key = f"btn_lock_plans_{abs(hash(feature_title)) % 100000}"
        if st.button("💎 View Plans & Activate Workspace", type="primary", key=btn_key, width="stretch"):
            st.session_state["pending_nav_page"] = "💎 SaaS Pricing"
            st.rerun()
