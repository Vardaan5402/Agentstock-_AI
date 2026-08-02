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

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.5-flash") -> None:
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
            "Fact references are advisory pointers and must use only allowed paths: "
            "/business/..., /policy/..., /inventory_risk/..., "
            "/purchase_options/{option_id}/..., or /simulations/{scenario_id}/.... "
            "Explain trade-offs using qualitative reasoning claims and evidence references. "
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


def request_structured_decision(
    facts: DecisionFacts, reasoner: StructuredReasoner
) -> LLMDecisionProposal:
    """Use an injected reasoner after deterministic facts have been assembled."""
    return reasoner.propose(facts)
