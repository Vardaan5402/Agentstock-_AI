"""Narrow optional Gemini explanation adapter for deterministic what-if results."""

import os
from typing import Protocol

from models.what_if import WhatIfComparisonResult, WhatIfExplanation


class WhatIfExplainer(Protocol):
    def explain(self, comparison: WhatIfComparisonResult) -> WhatIfExplanation: ...


class GeminiWhatIfExplainer:
    def __init__(self, api_key: str | None = None, model: str = "gemini-3.6-flash") -> None:
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY is required to create GeminiWhatIfExplainer")
        from google import genai
        self._client = genai.Client(api_key=key)
        self._model = model

    def explain(self, comparison: WhatIfComparisonResult) -> WhatIfExplanation:
        from google.genai import types
        prompt = (
            "Explain only verified qualitative before/after trade-offs in this immutable "
            "what-if comparison. Do not invent or output numerical facts. Use only valid "
            "comparison paths and return the structured schema.\n\n"
            + comparison.model_dump_json()
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=WhatIfExplanation,
                temperature=0.0,
            ),
        )
        return WhatIfExplanation.model_validate_json(response.text)


def validate_explanation_references(
    comparison: WhatIfComparisonResult, explanation: WhatIfExplanation
) -> tuple[bool, tuple[str, ...]]:
    """Validate advisory references against the deterministic comparison artifact."""
    errors: list[str] = []
    if explanation.scenario_id != comparison.scenario_id:
        errors.append("explanation scenario_id does not match comparison")
    allowed = {
        "/supplier_comparisons",
        "/baseline_outcome",
        "/counterfactual_outcome",
    }
    data = comparison.model_dump(mode="json")
    for i, claim in enumerate(explanation.explanation_claims):
        for ref in claim.fact_references:
            if not any(ref == root or ref.startswith(root + "/") for root in allowed):
                errors.append(f"claim {i} references unsupported fact path: {ref}")
                continue
            if not _resolves(data, ref):
                errors.append(f"claim {i} references nonexistent fact path: {ref}")
    return not errors, tuple(errors)


def _resolves(data: object, path: str) -> bool:
    parts = [x for x in path.split("/") if x]
    current = data
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return False
            current = current[part]
        elif isinstance(current, list):
            if part.isdigit() and int(part) < len(current):
                current = current[int(part)]
            else:
                return False
        else:
            return False
    return True
