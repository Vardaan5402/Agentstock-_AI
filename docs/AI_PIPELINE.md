# AgentStock AI — 5-Step Fact-Bounded AI Decision Pipeline

AgentStock AI employs a multi-stage pipeline that eliminates hallucinated inventory calculations by binding the generative model to deterministic mathematical ground truth.

```
[ Step 1: Fact Simulation ] ──> [ Step 2: Feasibility Audit ] ──> [ Step 3: Gemini Reasoning ]
                                                                               │
[ Step 5: Human Governance ] <── [ Step 4: Reference Verification ] <──────────┘
```

### Step 1: Fact Simulation (Deterministic Engine)
The Python deterministic simulator calculates runway days, safety stock deficit, recommended reorder quantities, and financial expenditure from live database parameters.

### Step 2: Policy & Constraint Feasibility Audit
The policy engine audits candidate supplier terms against business constraints (budget ceiling, minimum order quantity, lead times, and approval rules).

### Step 3: Gemini Structured Multimodal Reasoning
The calculated `DecisionFacts` JSON payload is provided to `gemini-2.5-flash` with strict instructions:
1. Do not calculate numbers.
2. Select the optimal supplier based strictly on lead-time vs. cost tradeoffs.
3. Return structured output adhering to the Pydantic schema.

### Step 4: Claim Reference Verification
Before displaying the recommendation, the system verifies every claim in the LLM response against the deterministic facts payload. Any claim referencing non-existent data is flagged and rejected.

### Step 5: Immutable Human-in-the-Loop Governance
All decisions are saved as immutable historical snapshots with cryptographic hashes. Autonomous order execution without human approval is strictly prevented.
