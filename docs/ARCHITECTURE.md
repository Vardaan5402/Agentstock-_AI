# AgentStock AI — System Architecture

## 1. Overview
AgentStock AI is an AI-powered inventory intelligence and supplier decision platform built for legitimate commercial enterprises, retail chains, and warehouse networks.

The core philosophy separates **Deterministic Math & Constraints** from **AI Contextual Reasoning**. Gemini never performs arithmetic, invents supplier metrics, or creates unconstrained proposals.

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT CLIENT UI                      │
│ (Landing, Dashboard, Camera, Voice, PO Dispatch, Admin)     │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    SECURITY & GATING LAYER                  │
│   - Salted PBKDF2 Password Verification                     │
│   - SHA-256 Hashed 6-Digit OTP                              │
│   - Sliding Window RateLimiter                              │
│   - Subscription & Metered Usage Gating                     │
│   - Multi-Tenant Ownership & IDOR Verification              │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                  DETERMINISTIC SIMULATION                   │
│   - Lead Time & Demand Runway Calculation                   │
│   - Stockout Risk & Safety Stock Deficit Analysis           │
│   - Supplier MOQ & Budget Constraint Solver                 │
│   - Counterfactual What-If Scenario Matrix                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                  GEMINI MULTIMODAL REASONING                │
│   - Structured JSON Output Schema                           │
│   - Reference Fact Claim Validation (Zero Hallucinations)   │
│   - Multilingual Speech-to-Intent Parser                    │
│   - Hybrid Computer Vision (Privacy Person Filter)          │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                   PERSISTENCE & DISPATCH                    │
│   - Multi-Tenant SQLite / PostgreSQL Schema                 │
│   - Immutable Audit Ledger & Decision Snapshots             │
│   - Multi-Channel PO Dispatch (WhatsApp, Email, Phone)     │
│   - Razorpay HMAC-SHA256 Webhook & Signature Verification   │
└─────────────────────────────────────────────────────────────┘
```

## 2. Core Modules
- **`core/calculations.py`**: Mathematical runway, reorder quantities, and stockout risk calculations.
- **`core/constraints.py`**: Business policy engine, budget ceiling, MOQ constraints, and human-in-the-loop governance.
- **`core/gemini_reasoner.py`**: Grounded structured reasoning using `gemini-2.5-flash`.
- **`core/gemini_inventory_vision.py`**: Hybrid computer vision with `PrivacyPersonFilter` and confidence scoring.
- **`core/voice_inventory.py`**: Multilingual speech translation and entity normalization.
- **`core/supplier_communication.py`**: PO order drafting, WhatsApp click-to-chat deep link generation, telephone dialers, and SMTP dispatch.
- **`core/document_processor.py`**: MIME-validated document parsing for invoices, receipts, and spreadsheets.
- **`core/chatbot.py`**: Domain-bounded conversational support chatbot.
- **`database/database.py`**: Multi-tenant database layer supporting thread-local SQLite (WAL mode) and PostgreSQL.
