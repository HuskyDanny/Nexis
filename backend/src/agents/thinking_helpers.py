"""Shared helpers and constants for the thinking pipeline agents."""

import json

THINKER_SKILLS = [
    "macro_economics",
    "geopolitical_risk",
    "sector_rotation",
    "regulatory_impact",
    "supply_chain",
    "consumer_behavior",
]

MATCHER_SKILLS = [
    "company_fundamentals",
    "technical_momentum",
    "sector_rotation",
]

# Confidence threshold below which the controller auto-stops
CONFIDENCE_THRESHOLD = 30


def convergence_score(sentiment: float, discount: float, agreement: float) -> float:
    """Deterministic convergence score: sentiment*0.3 + discount*0.3 + agreement*0.4."""
    return round(min(100.0, sentiment * 0.3 + discount * 0.3 + agreement * 0.4), 1)


def parse_json_response(raw: str) -> dict | None:
    """Extract and parse JSON from an LLM response string.

    Handles plain JSON and markdown code blocks (```json ... ```).
    Returns None if parsing fails.
    """
    if not raw or not raw.strip():
        return None

    text = raw.strip()

    # Handle markdown code blocks
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            # Strip language tag (e.g., "json")
            if inner.startswith("json"):
                inner = inner[4:]
            text = inner.strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
