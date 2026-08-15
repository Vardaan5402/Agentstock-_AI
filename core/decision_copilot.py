"""Gemini-powered, fact-bounded Decision Copilot."""

from __future__ import annotations

from core.gemini_reasoner import GeminiStructuredReasoner
from models.decision_workflow import DecisionWorkflowResult


class DecisionCopilot:
    """Answer human questions using only the current decision evidence."""

    def __init__(self, reasoner: GeminiStructuredReasoner) -> None:
        self.reasoner = reasoner

    def ask(
        self,
        result: DecisionWorkflowResult,
        question: str,
    ) -> str:
        """Return a Gemini explanation grounded in immutable decision facts."""

        question = question.strip()

        if not question:
            return "Please enter a question."

        facts = result.facts

        prompt = f"""
You are AgentStock AI Decision Copilot.

Your role is to explain an already-evaluated inventory decision
to a human reviewer.

IMPORTANT RULES:

1. The supplied DecisionFacts JSON is authoritative.
2. Do not invent facts.
3. Do not modify facts.
4. Do not calculate new business quantities.
5. Do not create a new purchase recommendation.
6. Do not introduce suppliers that are not present in the evidence.
7. Do not invent costs, quantities, dates, risks, or confidence values.
8. If the evidence does not support an answer, explicitly say:
   "The available decision evidence does not support answering that question."
9. Clearly distinguish evidence from interpretation.
10. Keep the answer concise and useful for a business reviewer.

Current decision status:
{result.status.value}

Current decision detail:
{result.status_detail}

Authoritative DecisionFacts:
{facts.canonical_json()}

Human reviewer question:
{question}

Answer the question using only the authoritative evidence above.
"""

        return self.reasoner.ask_copilot(prompt)