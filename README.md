# AgentStock AI

> **AI-powered inventory intelligence for modern businesses.**
> *See your stock. Understand your inventory. Act faster.*

AgentStock AI is an enterprise-grade inventory intelligence and supplier decision SaaS platform. It bridges physical stock management with automated supplier purchasing workflows, combining **deterministic inventory simulation**, **Gemini multimodal AI reasoning**, **privacy-first camera scanning**, **multilingual voice assistance**, and **1-click multi-channel PO dispatch** (WhatsApp, Email, Phone).

---

## ⚡ Key Capabilities

### 1. 📷 Privacy-First AI Camera Inventory Scanner
- Point mobile, tablet, or webcams at retail shelves, cartons, or barcodes.
- Powered by hybrid computer vision and Gemini 2.5/3.6 Flash multimodal extraction.
- **Privacy Person Detection**: Real-time filter automatically rejects and blurs frames containing human beings or faces. Zero facial recognition or worker surveillance.
- Pre-commit manual editing (e.g. adjust detected counts from 12 to 10 before saving).

### 2. 🎙️ Multilingual Voice Inventory Assistant
- Speak natural stock updates hands-free in English, Hindi (हिंदी), Spanish (Español), French (Français), Bengali (বাংলা), Marathi (मराठी), and 15+ global languages.
- Translates and normalizes colloquial phrases (e.g., *"Add 25 packets of basmati rice"* or *"25 packet rice add karo"*).
- Deterministic confirmation preview before mutating database records.

### 3. 🚚 Supplier Directory & Instant Multi-Channel PO Dispatch
- Complete directory tracking supplier phone numbers, GST IDs, lead times, and reliability scores.
- Automated professional Purchase Order drafting with itemization and pricing terms.
- **1-Click WhatsApp Dispatch**: Generates formatted click-to-chat deep links (`https://wa.me/...`).
- **SMTP Email Dispatch**: Instant order transmission via configured email server.
- **Direct Phone Dialer**: Native browser telephone dialer link (`tel:...`).
- Immutable communication audit trail.

### 4. 📄 Intelligent Document & Invoice OCR
- Upload PDF, CSV, XLSX, PNG, or JPG invoices and packing slips.
- Extracts structured inventory lines, SKUs, and unit costs with tenant directory isolation.

### 5. ⚙️ Fact-Bounded AI Decision Engine & What-If Simulator
- **Zero Numerical Hallucinations**: Gemini never calculates arithmetic or invents supplier parameters. The deterministic simulation engine computes all metrics first.
- **Reference Validation**: Rejects any LLM claim not explicitly present in the authoritative facts payload.
- **Counterfactual What-If Simulator**: Test price shocks, demand surges, and supplier lead-time delays against immutable baselines.
- **Human-in-the-Loop Governance**: Review-only recommendations requiring explicit human sign-off.

### 6. 💳 Enterprise Subscription Billing (Razorpay)
- Live Razorpay order creation, HMAC-SHA256 signature verification, and webhook handling.
- Flexible Starter, Professional, and Enterprise plans with monthly and annual billing.
- Promotional coupon engine (`LAUNCH50`, `SAVE20`).
- Server-side metered usage tracking for camera scans, voice commands, and decision analyses.

### 7. 👑 Platform Superadmin Console & Security Alert Stream
- Dedicated admin portal for platform management (`ADMIN_EMAIL` / `ADMIN_PASSWORD_HASH`).
- Telemetry KPIs, user role management, account locking, and security incident monitoring.
- Configurable GDPR data retention cleanup for audit ledgers.

---

## 🔒 Security & Privacy Architecture

- **Salted Password Hashing**: PBKDF2-HMAC-SHA256 with 260,000 iterations.
- **Secure OTPs**: 6-digit one-time codes stored as HMAC-SHA256 hashes (never plaintext).
- **Multi-Tenant Isolation**: Queries scoped to `user_id` and `business_id` to eliminate IDOR.
- **Rate Limiting**: Sliding-window rate limiters across auth and mutation endpoints.
- **Prompt Injection Defense**: Multi-layered boundary checks on user text prompts.
- **Self-Service GDPR Rights**: Complete JSON data export and account erasure.

---

## 🚀 Quickstart & Local Installation

### Prerequisites
- Python 3.10+
- SQLite 3.35+ or PostgreSQL 14+

### Setup
```bash
# 1. Clone the repository
git clone https://github.com/Vardaan5402/Agentstock-_AI.git
cd Agentstock-_AI

# 2. Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Fill in GEMINI_API_KEY, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, etc.

# 5. Run the Automated Test Suite (117 Tests)
python -m unittest discover -s . -p "test_*.py"

# 6. Launch the Streamlit SaaS Application
streamlit run app.py
```

---

## 🧪 Automated Test Suite

AgentStock AI includes 117 automated unit tests covering all deterministic models, simulations, security routines, and billing systems:

```bash
./.venv/bin/python -m unittest discover -s . -p "test_*.py"
```

| Test Suite | Purpose |
|---|---|
| `test_calculations.py` | Runway, reorder quantity, and stockout risk formulas |
| `test_constraints.py` | Policy ceilings, budget constraints, and MOQ checks |
| `test_decision_workflow.py` | 5-step fact-bounded decision pipeline |
| `test_what_if.py` | Counterfactual shock simulation and comparisons |
| `test_decision_persistence.py` | Immutable snapshots and audit logging |
| `test_razorpay_billing.py` | Razorpay order creation and HMAC-SHA256 verification |
| `test_coupons.py` | Discount percentages, caps, and plan restrictions |
| `test_auth_security.py` | PBKDF2 password hashing, OTP hashes, and rate limiting |
| `test_supplier_communication.py` | PO drafting, WhatsApp URLs, and soft delete |
| `test_document_processor.py` | MIME validation, CSV parsing, and XSS script rejection |
| `test_multilingual_voice.py` | Hindi, Spanish, and English voice command parsing |
| `test_camera_privacy.py` | Privacy person detection and frame warnings |
| `test_chatbot_moderation.py` | Acceptable use policy and prompt injection boundaries |
| `test_multi_tenant_database.py` | Tenant isolation, IDOR prevention, and GDPR export |

---

## ⚖️ License & Acceptable Use
This project is licensed under the commercial terms of AgentStock AI and is strictly restricted to legitimate business inventory management in accordance with our [Acceptable Use Policy](docs/ACCEPTABLE_USE_POLICY.md) and [Privacy Policy](docs/PRIVACY.md).
