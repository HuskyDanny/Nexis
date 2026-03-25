"""Shared helpers and constants for the thinking pipeline agents."""

import json
from uuid import uuid4

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
        reasoning = n.get("reasoning") or ""

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


def build_thinker_output(
    effects: list[dict],
    parent_nodes: list[dict],
    news_pool: list[dict],
    layer: int,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Construct nodes and edges from parsed thinker effects."""
    existing_ids = {n.get("id", "") for n in parent_nodes}
    effect_nodes: list[dict] = []
    fetch_nodes: list[dict] = []
    effect_edges: list[dict] = []
    fetch_edges: list[dict] = []

    for effect in effects:
        effect_id = uuid4().hex[:12]
        parent_ids = [
            pid for pid in effect.get("parent_ids", []) if pid in existing_ids
        ]
        if not parent_ids:
            parent_ids = [parent_nodes[0]["id"]]

        effect_nodes.append(
            {
                "id": effect_id,
                "layer": layer,
                "type": "effect",
                "content": effect.get("content", "Unknown effect"),
                "reasoning": effect.get("reasoning", ""),
                "confidence": effect.get("confidence", 50),
                "sources": [],
                "parents": parent_ids,
                "selected": True,
                "metadata": {
                    "sector": effect.get("sector", "general"),
                    "parent_count": len(parent_ids),
                    "information_gaps": effect.get("information_gaps", []),
                },
            }
        )

        for pid in parent_ids:
            effect_edges.append(
                {
                    "source": pid,
                    "target": effect_id,
                    "relationship": "causes" if layer == 1 else "compounds",
                }
            )

        # Handle fetched news references
        for fetched_id in effect.get("fetched_news_ids", []):
            if fetched_id in existing_ids:
                continue
            fetched_item = next(
                (n for n in news_pool if n.get("id") == fetched_id), None
            )
            if fetched_item:
                fetch_node_id = f"fetch-{uuid4().hex[:8]}"
                title = fetched_item.get("title", fetched_item.get("summary", ""))
                fetch_nodes.append(
                    {
                        "id": fetch_node_id,
                        "layer": layer,
                        "type": "fetch",
                        "content": f"Related: {title}",
                        "reasoning": "Agent fetched this news for context",
                        "confidence": 100,
                        "sources": [fetched_item.get("url", "")],
                        "parents": [parent_ids[0]],
                        "selected": True,
                        "metadata": fetched_item,
                    }
                )
                fetch_edges.append(
                    {
                        "source": parent_ids[0],
                        "target": fetch_node_id,
                        "relationship": "fetched_for",
                    }
                )
                existing_ids.add(fetched_id)

    return effect_nodes, fetch_nodes, effect_edges, fetch_edges


def build_matcher_output(
    matches: list[dict],
    effects: list[dict],
    value_pool: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Construct opportunity nodes and edges from parsed matcher output."""
    effect_map = {e.get("id", ""): e for e in effects}
    value_map = {v.get("ticker", ""): v for v in value_pool}

    opportunity_nodes: list[dict] = []
    new_edges: list[dict] = []

    for match in matches:
        ticker = match.get("ticker", "")
        effect_id = match.get("effect_id", "")

        if effect_id not in effect_map:
            continue
        val = value_map.get(ticker, {})
        if not val:
            continue

        parent_effect = effect_map[effect_id]
        opp_layer = parent_effect.get("layer", 1)

        sentiment = match.get("sentiment_score", 50.0)
        discount = val.get("discount_pct", 0)
        agreement = match.get("agreement_score", 50.0)
        score = convergence_score(sentiment, discount, agreement)

        opp_id = f"opp-{uuid4().hex[:8]}"
        opportunity_nodes.append(
            {
                "id": opp_id,
                "layer": opp_layer,
                "type": "opportunity",
                "content": f"{ticker} \u2014 {score}% conviction",
                "reasoning": match.get("reasoning", ""),
                "confidence": score,
                "sources": [],
                "parents": [effect_id],
                "selected": True,
                "metadata": {
                    **val,
                    "convergence_score": score,
                    "sentiment_score": sentiment,
                    "agreement_score": agreement,
                },
            }
        )
        new_edges.append(
            {"source": effect_id, "target": opp_id, "relationship": "matches"}
        )

    return opportunity_nodes, new_edges
