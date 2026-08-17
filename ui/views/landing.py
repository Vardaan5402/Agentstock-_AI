"""Welcome & Overview Portal for Visitors with Embedded Support Chatbot."""
import streamlit as st
from database.database import Database
from core.chatbot import AgentStockChatbot
from ui.components import render_section_header, render_pricing_card
from ui.views.auth import render_auth_form
from core.config import format_usd, get_plan_pricing


def _clean_html(html_str: str) -> str:
    return "\n".join(line.lstrip() for line in html_str.splitlines())


def _h(html_str: str):
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


def render_landing_page(database: Database):
    """Render commercial SaaS landing page for unauthenticated visitors."""
    # 1. Hero Section
    _h(
        """
        <div style="text-align: center; max-width: 900px; margin: 20px auto 40px auto; padding: 20px 10px;">
            <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(109, 93, 252, 0.12); border: 1px solid rgba(109, 93, 252, 0.35); padding: 6px 16px; border-radius: 999px; margin-bottom: 16px;">
                <span style="font-size: 11px; font-weight: 800; color: #00D4FF; letter-spacing: 0.1em; text-transform: uppercase;">
                    ⚡ AUTONOMOUS INVENTORY INTELLIGENCE
                </span>
            </div>
            <h1 style="font-size: 46px; font-weight: 800; letter-spacing: -0.03em; color: #FFFFFF; margin: 0; line-height: 1.15;">
                See your stock. Understand your inventory. <span style="background: linear-gradient(90deg, #6D5DFC, #00D4FF); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Act faster.</span>
            </h1>
            <p style="font-size: 18px; color: #CBD5E1; margin: 18px auto 28px auto; max-width: 720px; line-height: 1.6;">
                AgentStock AI empowers retail stores, warehouses, and D2C brands to prevent stockouts, scan inventory via camera, speak orders in their native language, and automate purchase orders with suppliers.
            </p>
        </div>
        """
    )

    # 2. CTA & Auth Section
    col_c1, col_c2, col_c3 = st.columns([1, 1.8, 1])
    with col_c2:
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center; margin-bottom: 4px; color: #FFFFFF;'>Get Started with AgentStock AI</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: var(--muted); font-size: 13px; margin-bottom: 16px;'>Create your business account or sign in to explore your inventory workspace.</p>", unsafe_allow_html=True)
            render_auth_form(database, key_prefix="landing_hero_auth")

    _h("<div style='height: 48px;'></div>")

    # 3. Core Feature Pillars
    render_section_header("Engineered for Modern Business Operations", "Everything you need to automate inventory and supplier decisions", "⚡")

    f1, f2, f3 = st.columns(3)
    with f1:
        _h(
            """
            <div class="agent-card" style="height: 100%; border-top: 3px solid #6D5DFC;">
                <div style="font-size: 28px; margin-bottom: 10px;">📷</div>
                <div style="font-size: 18px; font-weight: 800; color: #FFFFFF; margin-bottom: 6px;">
                    AI Camera Inventory Scanner
                </div>
                <p style="font-size: 13px; color: var(--muted); line-height: 1.6;">
                    Point your camera at shelves, boxes, or barcodes. Our hybrid computer vision and Gemini multimodal AI counts on-hand units with strict privacy person detection.
                </p>
            </div>
            """
        )
    with f2:
        _h(
            """
            <div class="agent-card" style="height: 100%; border-top: 3px solid #00D4FF;">
                <div style="font-size: 28px; margin-bottom: 10px;">🎙️</div>
                <div style="font-size: 18px; font-weight: 800; color: #FFFFFF; margin-bottom: 6px;">
                    Multilingual Voice Assistant
                </div>
                <p style="font-size: 13px; color: var(--muted); line-height: 1.6;">
                    Speak in English, Hindi, Spanish, French, Bengali, and 15+ languages. Say <em>"Add 25 packets of basmati rice"</em> to update inventory hands-free with confirmation.
                </p>
            </div>
            """
        )
    with f3:
        _h(
            """
            <div class="agent-card" style="height: 100%; border-top: 3px solid #22C55E;">
                <div style="font-size: 28px; margin-bottom: 10px;">📞</div>
                <div style="font-size: 18px; font-weight: 800; color: #FFFFFF; margin-bottom: 6px;">
                    1-Click Supplier PO Dispatch
                </div>
                <p style="font-size: 13px; color: var(--muted); line-height: 1.6;">
                    Automatically generate professional purchase orders when stock runs low. Dispatch directly to suppliers via WhatsApp, Email, or direct Phone calls.
                </p>
            </div>
            """
        )

    _h("<div style='height: 48px;'></div>")

    # 4. Transparent Commercial Pricing
    render_section_header("Simple, Transparent Pricing", "Choose the plan that fits your business scale", "💎")

    p1, p2, p3 = st.columns(3)
    with p1:
        render_pricing_card(
            title="STARTER",
            price=format_usd(get_plan_pricing("STARTER")["monthly_usd"]),
            period="/ month",
            description="For small retail shops & single-location stores",
            features=[
                "1 Business Location",
                "100 AI Camera Scans / mo",
                "250 Voice Queries / mo",
                "500 AI Decision Analyses",
                "WhatsApp & Phone PO Dispatch",
                "Standard Email Support",
            ],
            is_popular=False,
            button_text="Get Started with Starter",
            key="landing_p_starter",
        )
    with p2:
        render_pricing_card(
            title="PROFESSIONAL",
            price=format_usd(get_plan_pricing("PROFESSIONAL")["monthly_usd"]),
            period="/ month",
            description="For growing brands & multi-supplier networks",
            features=[
                "Unlimited Business Locations",
                "1,000 AI Camera Scans / mo",
                "1,500 Voice Queries / mo",
                "Unlimited AI Decision Analyses",
                "What-If Counterfactual Simulations",
                "Document & Invoice OCR Parsing",
                "Priority 24/7 Support",
            ],
            is_popular=True,
            button_text="Get Started with Professional",
            key="landing_p_pro",
        )
    with p3:
        render_pricing_card(
            title="ENTERPRISE",
            price=format_usd(get_plan_pricing("ENTERPRISE")["monthly_usd"]),
            period="/ month",
            description="For high-volume warehouse & supply networks",
            features=[
                "Unlimited Everything",
                "Custom Gemini Multimodal Models",
                "Automated ERP & API Integrations",
                "Multi-Tenant RBAC Governance",
                "Dedicated Account Manager",
                "99.9% Uptime SLA",
            ],
            is_popular=False,
            button_text="Contact Enterprise",
            key="landing_p_enterprise",
        )

    _h("<div style='height: 48px;'></div>")

    # 5. AI Support Chatbot (No Login Required)
    render_section_header("Have Questions? Ask AgentStock AI Support", "Instant assistance for plans, features, camera scanning, and payments", "🤖")

    col_bot1, col_bot2 = st.columns([1.8, 1])
    with col_bot1:
        st.markdown("**💬 Ask AgentStock Assistant:**")
        user_q = st.text_input(
            "Type your question:",
            placeholder="e.g., How does the AI camera scanner count items? or What is included in the Professional plan?",
            key="landing_chatbot_query",
        )
        if st.button("Ask Assistant ➔", type="primary", key="landing_btn_ask"):
            if user_q.strip():
                bot = AgentStockChatbot()
                with st.spinner("AgentStock Assistant is thinking..."):
                    answer = bot.ask(user_q)
                _h(
                    f"""
                    <div style="background: rgba(109, 93, 252, 0.12); border: 1.5px solid rgba(109, 93, 252, 0.4); border-radius: 14px; padding: 16px 20px; margin-top: 14px;">
                        <div style="font-size: 12px; font-weight: 700; color: #00D4FF; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px;">
                            🤖 AGENTSTOCK ASSISTANT
                        </div>
                        <div style="font-size: 14px; color: #FFFFFF; line-height: 1.6;">
                            {answer}
                        </div>
                    </div>
                    """
                )
    with col_bot2:
        _h(
            """
            <div class="agent-card" style="padding: 16px;">
                <div style="font-size: 14px; font-weight: 700; color: #FFFFFF; margin-bottom: 8px;">
                    💡 Popular Questions
                </div>
                <div style="font-size: 13px; color: var(--muted); line-height: 1.7;">
                    • How does the Camera Scanner prevent privacy leaks?<br/>
                    • What languages are supported for voice?<br/>
                    • How are payments processed with Razorpay?<br/>
                    • Can I export or delete my business data?
                </div>
            </div>
            """
        )

    _h("<div style='height: 48px;'></div>")

    # 6. Trust & Acceptable Use Policy Footer
    _h(
        """
        <div style="border-top: 1px solid var(--border); padding-top: 24px; text-align: center; font-size: 13px; color: var(--muted);">
            <div>
                © 2026 <strong>AgentStock AI</strong>. All rights reserved. • Strictly bounded for legitimate commercial inventory management.
            </div>
            <div style="margin-top: 8px;">
                <span style="color: var(--accent);">Acceptable Use Policy</span> •
                <span style="color: var(--accent);">Privacy Policy</span> •
                <span style="color: var(--accent);">Terms of Service</span> •
                <span style="color: var(--accent);">Security</span>
            </div>
        </div>
        """
    )
