import streamlit as st

def _clean_html(html_str: str) -> str:
    """Strip leading whitespace from every line so Streamlit markdown never triggers code blocks."""
    return "\n".join(line.lstrip() for line in html_str.splitlines())

def inject_theme():
    st.markdown(
        _clean_html(
            """
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

            /* =========================================================
               AGENTSTOCK AI — ENTERPRISE COMMERCIAL SaaS DESIGN SYSTEM
               ========================================================= */

            :root {
                --primary: #6D5DFC;
                --primary-light: #8B7CFF;
                --primary-glow: rgba(109, 93, 252, 0.25);
                --accent: #00D4FF;
                --accent-glow: rgba(0, 212, 255, 0.2);
                --success: #22C55E;
                --success-glow: rgba(34, 197, 94, 0.2);
                --warning: #F59E0B;
                --warning-glow: rgba(245, 158, 11, 0.2);
                --danger: #EF4444;
                --danger-glow: rgba(239, 68, 68, 0.2);

                --bg: #070B14;
                --surface: #0D1422;
                --surface-2: #111A2B;
                --surface-hover: #162238;
                --border: rgba(255, 255, 255, 0.08);
                --border-light: rgba(255, 255, 255, 0.15);

                --text: #F8FAFC;
                --text-secondary: #CBD5E1;
                --muted: #94A3B8;

                --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
                --font-mono: 'JetBrains Mono', monospace;
            }

            /* ---------- GLOBAL ---------- */

            html, body, [class*="css"], .stApp {
                font-family: var(--font-sans);
                color: var(--text);
                background-color: var(--bg);
            }

            .stApp {
                background:
                    radial-gradient(circle at 12% 10%, rgba(109, 93, 252, 0.14), transparent 32%),
                    radial-gradient(circle at 88% 18%, rgba(0, 212, 255, 0.09), transparent 28%),
                    radial-gradient(circle at 50% 85%, rgba(34, 197, 94, 0.05), transparent 35%),
                    var(--bg);
                background-attachment: fixed;
            }

            /* ---------- STREAMLIT CHROME & SIDEBAR TOGGLE ---------- */

            #MainMenu, footer {
                display: none !important;
            }

            header[data-testid="stHeader"] {
                background: transparent !important;
                z-index: 99999 !important;
            }

            /* Make sure the collapsed control (sidebar open button) is ALWAYS visible */
            [data-testid="collapsedControl"],
            [data-testid="stSidebarCollapseButton"] {
                display: flex !important;
                visibility: visible !important;
                opacity: 1 !important;
                z-index: 999999 !important;
            }

            [data-testid="collapsedControl"] button,
            [data-testid="stSidebarCollapseButton"] button {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                visibility: visible !important;
                opacity: 1 !important;
                background: linear-gradient(135deg, #6D5DFC 0%, #00D4FF 100%) !important;
                color: #FFFFFF !important;
                border: 1px solid rgba(255, 255, 255, 0.4) !important;
                border-radius: 10px !important;
                padding: 6px 12px !important;
                min-width: 38px !important;
                min-height: 38px !important;
                box-shadow: 0 4px 15px rgba(109, 93, 252, 0.6) !important;
                cursor: pointer !important;
            }

            [data-testid="collapsedControl"] button *,
            [data-testid="stSidebarCollapseButton"] button * {
                color: #FFFFFF !important;
                fill: #FFFFFF !important;
                stroke: #FFFFFF !important;
                visibility: visible !important;
                opacity: 1 !important;
            }

            [data-testid="collapsedControl"] svg,
            [data-testid="stSidebarCollapseButton"] svg {
                width: 22px !important;
                height: 22px !important;
                display: block !important;
                fill: #FFFFFF !important;
                color: #FFFFFF !important;
            }

            /* ---------- MAIN CONTAINER ---------- */

            .block-container {
                max-width: 1440px;
                padding-top: 1.5rem;
                padding-bottom: 4rem;
                padding-left: 2rem;
                padding-right: 2rem;
            }

            /* ---------- SIDEBAR NAVIGATION ---------- */

            section[data-testid="stSidebar"] {
                background: linear-gradient(180deg, #090E1A 0%, #060912 100%) !important;
                border-right: 1px solid var(--border) !important;
                box-shadow: 5px 0 25px rgba(0,0,0,0.4);
            }

            section[data-testid="stSidebar"] > div {
                padding-top: 1.25rem;
            }

            /* ---------- BRAND LOGO HEADER ---------- */

            .brand-header {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 12px 16px;
                margin-bottom: 24px;
                background: linear-gradient(135deg, rgba(109, 93, 252, 0.15), rgba(0, 212, 255, 0.08));
                border: 1px solid rgba(109, 93, 252, 0.3);
                border-radius: 16px;
            }

            .brand-icon {
                font-size: 28px;
                background: linear-gradient(135deg, var(--primary-light), var(--accent));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }

            .brand-name {
                font-weight: 800;
                font-size: 19px;
                letter-spacing: -0.02em;
                color: #FFFFFF;
            }

            .brand-tag {
                font-size: 11px;
                font-weight: 600;
                color: var(--accent);
                text-transform: uppercase;
                letter-spacing: 0.1em;
            }

            /* ---------- SYSTEM STATUS BAR ---------- */

            .status-pill {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 6px 14px;
                border-radius: 999px;
                background: rgba(34, 197, 94, 0.1);
                border: 1px solid rgba(34, 197, 94, 0.3);
                color: #4ADE80;
                font-size: 12px;
                font-weight: 600;
            }

            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background-color: var(--success);
                box-shadow: 0 0 10px var(--success);
                animation: pulse-dot 2s infinite;
            }

            /* ---------- CARDS & PANELS ---------- */

            .agent-card {
                background: linear-gradient(145deg, rgba(17, 26, 43, 0.95), rgba(9, 14, 25, 0.95));
                border: 1px solid var(--border);
                border-radius: 20px;
                padding: 24px;
                box-shadow: 0 15px 35px rgba(0, 0, 0, 0.25);
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
                margin-bottom: 20px;
                backdrop-filter: blur(10px);
            }

            .agent-card:hover {
                border-color: rgba(109, 93, 252, 0.4);
                box-shadow: 0 20px 45px rgba(109, 93, 252, 0.12);
                transform: translateY(-2px);
            }

            .hero-card {
                position: relative;
                overflow: hidden;
                background:
                    radial-gradient(circle at 90% 20%, rgba(109, 93, 252, 0.25), transparent 40%),
                    radial-gradient(circle at 10% 80%, rgba(0, 212, 255, 0.15), transparent 35%),
                    linear-gradient(135deg, #111A2B 0%, #090F1B 100%);
                border: 1px solid rgba(109, 93, 252, 0.45);
                border-radius: 24px;
                padding: 32px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4), 0 0 40px rgba(109, 93, 252, 0.15);
                margin-bottom: 24px;
            }

            .hero-badge {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 6px 14px;
                border-radius: 999px;
                background: linear-gradient(90deg, rgba(109, 93, 252, 0.2), rgba(0, 212, 255, 0.2));
                border: 1px solid rgba(109, 93, 252, 0.5);
                color: #C4B5FD;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 16px;
            }

            .hero-title {
                font-size: clamp(28px, 3.5vw, 44px);
                font-weight: 800;
                letter-spacing: -0.03em;
                background: linear-gradient(90deg, #FFFFFF 0%, #E2E8F0 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 8px;
            }

            .hero-supplier-name {
                font-size: clamp(32px, 4vw, 54px);
                font-weight: 800;
                letter-spacing: -0.03em;
                background: linear-gradient(90deg, #4ADE80 0%, #38BDF8 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-top: 4px;
                margin-bottom: 16px;
            }

            /* ---------- METRIC CARDS ---------- */

            .metric-card {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 16px;
                padding: 18px 20px;
                transition: all 0.2s ease;
            }

            .metric-card:hover {
                background: rgba(255, 255, 255, 0.05);
                border-color: rgba(255, 255, 255, 0.12);
            }

            .metric-label {
                font-size: 13px;
                font-weight: 500;
                color: var(--muted);
                margin-bottom: 6px;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }

            .metric-value {
                font-size: 26px;
                font-weight: 700;
                color: #FFFFFF;
                letter-spacing: -0.02em;
            }

            .metric-sub {
                font-size: 12px;
                color: var(--text-secondary);
                margin-top: 4px;
            }

            /* ---------- BADGES & CHIPS ---------- */

            .badge {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 5px 12px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: 600;
            }

            .badge-success {
                background: rgba(34, 197, 94, 0.12);
                border: 1px solid rgba(34, 197, 94, 0.3);
                color: #4ADE80;
            }

            .badge-warning {
                background: rgba(245, 158, 11, 0.12);
                border: 1px solid rgba(245, 158, 11, 0.3);
                color: #FBBF24;
            }

            .badge-danger {
                background: rgba(239, 68, 68, 0.12);
                border: 1px solid rgba(239, 68, 68, 0.3);
                color: #F87171;
            }

            .badge-primary {
                background: rgba(109, 93, 252, 0.15);
                border: 1px solid rgba(109, 93, 252, 0.35);
                color: #A78BFA;
            }

            .badge-info {
                background: rgba(0, 212, 255, 0.12);
                border: 1px solid rgba(0, 212, 255, 0.3);
                color: #38BDF8;
            }

            /* ---------- WHAT-IF DELTA CARDS ---------- */

            .delta-card {
                background: var(--surface);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 20px;
                margin-bottom: 12px;
            }

            .delta-improved {
                border-left: 4px solid var(--success) !important;
                background: linear-gradient(90deg, rgba(34, 197, 94, 0.06), var(--surface));
            }

            .delta-worsened {
                border-left: 4px solid var(--danger) !important;
                background: linear-gradient(90deg, rgba(239, 68, 68, 0.06), var(--surface));
            }

            .delta-neutral {
                border-left: 4px solid var(--muted) !important;
            }

            /* ---------- AI PIPELINE BANNER & GOVERNANCE ---------- */

            .pipeline-container {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 8px;
                padding: 20px 24px;
                background: linear-gradient(90deg, rgba(13, 20, 34, 0.9), rgba(17, 26, 43, 0.9));
                border: 1px solid var(--border);
                border-radius: 20px;
                margin-bottom: 28px;
                overflow-x: auto;
            }

            .pipeline-step {
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
                flex: 1;
                min-width: 110px;
            }

            .pipeline-icon {
                width: 44px;
                height: 44px;
                border-radius: 50%;
                background: rgba(109, 93, 252, 0.12);
                border: 1px solid rgba(109, 93, 252, 0.3);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
                color: var(--primary-light);
                margin-bottom: 8px;
                transition: all 0.3s ease;
            }

            .pipeline-step.active .pipeline-icon {
                background: var(--primary);
                color: #FFFFFF;
                box-shadow: 0 0 15px var(--primary-glow);
            }

            .pipeline-step.success .pipeline-icon {
                background: rgba(34, 197, 94, 0.15);
                border-color: rgba(34, 197, 94, 0.4);
                color: #4ADE80;
            }

            .pipeline-label {
                font-size: 12px;
                font-weight: 700;
                color: var(--text-secondary);
            }

            .pipeline-sub {
                font-size: 10px;
                color: var(--muted);
            }

            .pipeline-arrow {
                color: var(--muted);
                font-size: 16px;
                opacity: 0.5;
            }

            /* ---------- PRICING CARDS ---------- */

            .pricing-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 24px;
                margin-top: 24px;
            }

            .pricing-card {
                background: var(--surface);
                border: 1px solid var(--border);
                border-radius: 24px;
                padding: 32px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                position: relative;
                transition: all 0.3s ease;
            }

            .pricing-card:hover {
                transform: translateY(-4px);
                border-color: var(--primary-light);
                box-shadow: 0 20px 50px rgba(109, 93, 252, 0.15);
            }

            .pricing-card.popular {
                border: 2px solid var(--primary);
                background: linear-gradient(145deg, rgba(17, 26, 43, 0.98), rgba(13, 20, 34, 0.98));
                box-shadow: 0 15px 40px rgba(109, 93, 252, 0.2);
            }

            .popular-badge {
                position: absolute;
                top: -14px;
                right: 24px;
                background: linear-gradient(90deg, var(--primary), var(--accent));
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 800;
                padding: 4px 14px;
                border-radius: 999px;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }

            .price-title {
                font-size: 22px;
                font-weight: 800;
                color: #FFFFFF;
                margin-bottom: 8px;
            }

            .price-amount {
                font-size: 38px;
                font-weight: 800;
                color: #FFFFFF;
                margin-bottom: 4px;
            }

            .price-period {
                font-size: 14px;
                color: var(--muted);
            }

            .price-features {
                list-style: none;
                padding: 0;
                margin: 24px 0;
            }

            .price-features li {
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 14px;
                color: var(--text-secondary);
                margin-bottom: 12px;
            }

            .price-features li span {
                color: var(--success);
                font-weight: 700;
            }

            /* ---------- COPILOT CHAT ---------- */

            .chat-bubble-user {
                background: rgba(109, 93, 252, 0.15);
                border: 1px solid rgba(109, 93, 252, 0.3);
                border-radius: 16px 16px 4px 16px;
                padding: 14px 18px;
                margin-bottom: 12px;
                max-width: 85%;
                margin-left: auto;
                color: #F1F5F9;
                font-size: 14px;
            }

            .chat-bubble-ai {
                background: rgba(17, 26, 43, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px 16px 16px 4px;
                padding: 16px 20px;
                margin-bottom: 16px;
                max-width: 90%;
                color: #F8FAFC;
                font-size: 14px;
                line-height: 1.6;
            }

            /* ---------- STREAMLIT FORM & BUTTON OVERRIDES ---------- */

            .stButton > button {
                border-radius: 12px !important;
                min-height: 46px !important;
                font-weight: 650 !important;
                font-family: var(--font-sans) !important;
                transition: all 0.2s ease !important;
            }

            .stButton > button[kind="primary"] {
                background: linear-gradient(135deg, #6D5DFC 0%, #5B4BF0 100%) !important;
                border: 1px solid rgba(139, 124, 255, 0.4) !important;
                box-shadow: 0 4px 20px rgba(109, 93, 252, 0.3) !important;
                color: #FFFFFF !important;
            }

            .stButton > button[kind="primary"]:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 8px 30px rgba(109, 93, 252, 0.45) !important;
                background: linear-gradient(135deg, #7B6DFF 0%, #6D5DFC 100%) !important;
            }

            .stButton > button[kind="secondary"] {
                background: rgba(255, 255, 255, 0.05) !important;
                border: 1px solid var(--border-light) !important;
                color: var(--text) !important;
            }

            .stButton > button[kind="secondary"]:hover {
                background: rgba(255, 255, 255, 0.1) !important;
                border-color: rgba(255, 255, 255, 0.25) !important;
                transform: translateY(-1px) !important;
            }

            div[data-baseweb="input"], div[data-baseweb="select"] > div {
                border-radius: 12px !important;
                background-color: rgba(13, 20, 34, 0.8) !important;
                border-color: var(--border) !important;
            }

            div[data-baseweb="input"]:focus-within, div[data-baseweb="select"]:focus-within {
                border-color: var(--primary) !important;
                box-shadow: 0 0 0 2px var(--primary-glow) !important;
            }

            /* ---------- ANIMATIONS ---------- */

            @keyframes pulse-ring {
                0%, 100% { transform: scale(0.96); opacity: 0.4; }
                50% { transform: scale(1.06); opacity: 0.85; }
            }

            @keyframes pulse-dot {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.4; transform: scale(0.85); }
            }

            .pulse-ring-effect {
                animation: pulse-ring 4s ease-in-out infinite;
            }

            /* ---------- RESPONSIVE BREAKPOINTS ---------- */

            @media (max-width: 1024px) {
                .block-container { padding-left: 1rem; padding-right: 1rem; }
                .hero-title { font-size: 32px; }
                .hero-supplier-name { font-size: 40px; }
            }

            @media (max-width: 768px) {
                .pipeline-container { gap: 16px; justify-content: flex-start; }
                .pricing-grid { grid-template-columns: 1fr; }
                .metric-card { padding: 14px; }
                .metric-value { font-size: 22px; }
            }

            </style>
            """
        ),
        unsafe_allow_html=True,
    )