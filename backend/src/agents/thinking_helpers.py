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


# Max chars for reasoning on older parent nodes (>1 layer behind current).
_REASONING_TRUNCATE_LIMIT = 200


def prepare_parent_nodes(parent_nodes: list[dict], current_layer: int) -> list[dict]:
    """Prepare parent nodes for the Thinker prompt, truncating old reasoning.

    Nodes from the immediately preceding layer keep full reasoning.
    Older nodes get reasoning truncated to ``_REASONING_TRUNCATE_LIMIT`` chars
    to prevent context window overflow at deeper layers.
    """
    prepared = []
    for n in parent_nodes:
        node_layer = n.get("layer")
        reasoning = n.get("reasoning", "")

        # Truncate reasoning for nodes >1 layer behind current layer.
        # Nodes without a 'layer' field are kept full (safe fallback).
        if (
            node_layer is not None
            and current_layer - node_layer > 1
            and len(reasoning) > _REASONING_TRUNCATE_LIMIT
        ):
            reasoning = reasoning[:_REASONING_TRUNCATE_LIMIT] + "…"

        prepared.append(
            {
                "id": n.get("id", ""),
                "content": n.get("content", ""),
                "reasoning": reasoning,
                "confidence": n.get("confidence", 50),
                "metadata": n.get("metadata", {}),
            }
        )
    return prepared


def parse_json_response(raw: str) -> dict | None:
    """Extract and parse JSON from an LLM response string.

    Handles:
    - Plain JSON
    - Markdown code blocks (```json ... ```)
    - Responses interleaved with XML tool calls (e.g., <minimax:tool_call>)
    - JSON embedded in prose text

    Returns None if no valid JSON object can be found.
    """
    if not raw or not raw.strip():
        return None

    text = raw.strip()

    # Strategy 1: Handle markdown code blocks
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            try:
                return json.loads(inner.strip())
            except (json.JSONDecodeError, ValueError):
                pass

    # Strategy 2: Try parsing the whole text as JSON
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 3: Strip XML-like tool call blocks and retry
    import re

    cleaned = re.sub(
        r"<[^>]+:tool_call>.*?</[^>]+:tool_call>", "", text, flags=re.DOTALL
    )
    cleaned = cleaned.strip()
    if cleaned and cleaned != text:
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 4: Find the first top-level JSON object via brace matching
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except (json.JSONDecodeError, ValueError):
                        break

    return None
