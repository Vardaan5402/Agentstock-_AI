# AgentStock AI

> An AI-powered inventory intelligence and decision-support system for businesses — combining deterministic inventory analytics, supplier constraint evaluation, counterfactual simulation, and structured Gemini reasoning.

AgentStock AI is designed to help businesses understand **when inventory risk is emerging, what purchasing options are available, what could happen under different scenarios, and why a particular decision may make sense**.

The system intentionally separates deterministic business logic from AI reasoning: numerical calculations, feasibility checks, simulations, and policy validation remain deterministic, while Gemini is used for structured qualitative reasoning over verified facts.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)]()
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)]()
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-4285F4?logo=google&logoColor=white)]()
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)]()
[![Pydantic](https://img.shields.io/badge/Validation-Pydantic-E92063)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

---

## 🚀 Overview

Inventory decisions look simple on the surface:

> **"Which supplier should I purchase from?"**

In reality, the decision can depend on:

- Current inventory
- Daily demand
- Safety stock
- Supplier pricing
- Minimum order quantities
- Supplier reliability
- Supplier lead time
- Budget constraints
- Expected stockout risk
- Purchase timing
- Policy restrictions
- Operational feasibility
- Financial feasibility
- Uncertainty in the available data

Traditional inventory software often provides dashboards and raw numbers.

AgentStock AI goes one step further.

It creates a **decision intelligence layer** between business data and human action.

Instead of simply saying:

> "Buy from Supplier A."

AgentStock AI attempts to answer:

> **"What should I do, why should I do it, what evidence supports that decision, what could go wrong, and should a human approve it?"**

---

# 🎯 The Problem

Small and medium-sized businesses frequently make inventory decisions using spreadsheets, intuition, messaging applications, phone calls, and disconnected supplier information.

This creates several problems:

### 1. Stockouts

Businesses may discover too late that inventory will not last until the next supplier delivery.

### 2. Excess Inventory

Ordering too much inventory ties up working capital and increases storage costs.

### 3. Supplier Complexity

The cheapest supplier isn't always the best supplier.

A supplier with a lower price may have:

- Longer lead time
- Lower reliability
- Higher MOQ
- Greater operational risk

### 4. Budget Constraints

A theoretically optimal purchase may still be financially impossible.

### 5. Black-Box AI

A language model may produce a convincing recommendation that isn't actually supported by the underlying business data.

### 6. Lack of Auditability

Businesses need to know:

- What data was used?
- What recommendation was generated?
- Which scenario was selected?
- What assumptions were made?
- Why was the recommendation accepted or rejected?
- What did the system know at that moment?

AgentStock AI is designed around these problems.

---

# 💡 The AgentStock AI Approach

AgentStock AI combines:

```text
Business Data
     ↓
Deterministic Calculations
     ↓
Inventory Risk Analysis
     ↓
Supplier Feasibility
     ↓
Scenario Simulation
     ↓
Evidence Snapshot
     ↓
Google Gemini Reasoning
     ↓
Reference Validation
     ↓
Policy Validation
     ↓
Human Review
     ↓
Audit Trail
