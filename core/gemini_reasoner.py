"""Narrow Gemini adapter for structured, fact-bounded decision reasoning."""

import os
from typing import Protocol

from models.decision_intelligence import DecisionFacts, LLMDecisionProposal


class StructuredReasoner(Protocol):
    """An injectable interface that enables deterministic tests without Gemini."""

    def propose(self, facts: DecisionFacts) -> LLMDecisionProposal:
        """Return a structured proposal from a validated deterministic snapshot."""


class GeminiStructuredReasoner:
    """Gemini adapter that sends facts, never delegates calculations to the model."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-3.6-flash") -> None:
        resolved_api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_api_key:
            raise ValueError("GEMINI_API_KEY is required to create GeminiStructuredReasoner")
        from google import genai

        self._client = genai.Client(api_key=resolved_api_key)
        self._model = model

    def propose(self, facts: DecisionFacts) -> LLMDecisionProposal:
        """Request only the narrow schema; no numerical fields exist in the output."""
        from google.genai import types

        prompt = (
            "You are a decision-reasoning assistant. The supplied JSON is the complete "
            "authoritative fact snapshot. Do not calculate, invent, alter, or output any "
            "numerical business facts. Select only an ID from eligible_scenario_ids. "

            "Fact references are advisory pointers. A fact reference MUST resolve to an "
            "actual field present in the supplied DECISION_FACTS_JSON. NEVER invent, "
            "guess, fabricate, or create a placeholder path. NEVER append descriptive "
            "text to a valid path. Before returning a fact reference, verify that every "
            "path component exists in the supplied JSON. "

            "Allowed roots are only: "
            "/business/..., /policy/..., /inventory_risk/..., "
            "/purchase_options/{option_id}/..., or /simulations/{scenario_id}/.... "

            "For example, if a simulation contains fields such as action_type, "
            "supplier_id, arrival_day, stockout_day, ending_inventory, "
            "total_shortage_units, or purchase_cost, you may reference those exact "
            "fields. Do not reference a field that is not present. "

            "If there is no useful exact fact-reference path for a reasoning claim, "
            "leave fact_references empty rather than inventing one. "

            "Compared scenario IDs must also be actual scenario IDs from the supplied "
            "simulations. Do not invent scenario IDs. "

            "Explain trade-offs using qualitative reasoning claims and verified evidence. "
            "Return only the requested structured schema.\n\n"

            f"DECISION_FACTS_JSON:\n{facts.canonical_json()}"
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LLMDecisionProposal,
                temperature=0.0,
            ),
        )
        return LLMDecisionProposal.model_validate_json(response.text)

    def ask_copilot(self, prompt: str) -> str:
        """Answer a fact-bounded human-review question."""
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
            ),
        )

        if not response.text:
            raise ValueError("Gemini returned an empty copilot response")

        return response.text.strip()

def request_structured_decision(
    facts: DecisionFacts, reasoner: StructuredReasoner
) -> LLMDecisionProposal:
    """Use an injected reasoner after deterministic facts have been assembled."""
    return reasoner.propose(facts)
