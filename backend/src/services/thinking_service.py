"""Thinking service — orchestrates agent reasoning or falls back to mock.

This is the integration layer between the API and the agent crews.
When SILICONFLOW_API_KEY is set, uses real CrewAI agents.
When not set, uses deterministic mock for development/testing.
"""

import random
from uuid import uuid4

from src.core.logger import get_logger

log = get_logger("thinking.service")


def _use_real_agents() -> bool:
    """Check if real agents are available."""
    try:
        from src.agents.llm_config import is_llm_available

        return is_llm_available()
    except ImportError:
        return False


def _mock_think_effects(
    parent_nodes: list[dict],
    news_pool: list[dict],
    current_layer_nodes: list[dict],
    next_layer: int,
    existing_ids: set[str],
) -> tuple[list[dict], list[dict]]:
    """Mock reasoning — deterministic sector-based effects."""
    new_nodes = []
    new_edges = []

    # Group by sector for compound effects
    sector_nodes: dict[str, list[dict]] = {}
    for parent in current_layer_nodes:
        sectors = parent.get("metadata", {}).get("sectors", [])
        sector = parent.get("metadata", {}).get("sector", "")
        if sectors:
            for s in sectors:
                sector_nodes.setdefault(s, []).append(parent)
        elif sector:
            sector_nodes.setdefault(sector, []).append(parent)
        else:
            sector_nodes.setdefault("general", []).append(parent)

    created: set[str] = set()
    for sector, parents in sector_nodes.items():
        if sector in created:
            continue
        created.add(sector)

        eid = uuid4().hex[:12]
        pids = [p["id"] for p in parents]
        pcontents = [p["content"][:30] for p in parents]

        new_nodes.append(
            {
                "id": eid,
                "layer": next_layer,
                "type": "effect",
                "content": f"Impact on {sector}: {' + '.join(pcontents)}",
                "reasoning": f"Compound effect from {len(parents)} sources on {sector} sector",
                "sources": [s for p in parents for s in p.get("sources", [])],
                "parents": pids,
                "selected": True,
                "metadata": {"sector": sector, "parent_count": len(parents)},
            }
        )
        for pid in pids:
            new_edges.append(
                {
                    "source": pid,
                    "target": eid,
                    "relationship": "causes" if next_layer == 1 else "compounds",
                }
            )

    # Fetch a related news item
    available = [n for n in news_pool if n["id"] not in existing_ids]
    if available and current_layer_nodes:
        fetched = random.choice(available)
        fid = f"fetch-{uuid4().hex[:8]}"
        new_nodes.append(
            {
                "id": fid,
                "layer": next_layer,
                "type": "fetch",
                "content": f"Related: {fetched.get('title', fetched.get('summary', ''))}",
                "reasoning": "Agent fetched this related news for additional context",
                "sources": [fetched.get("url", "")],
                "parents": [current_layer_nodes[0]["id"]],
                "selected": True,
                "metadata": fetched,
            }
        )
        new_edges.append(
            {
                "source": current_layer_nodes[0]["id"],
                "target": fid,
                "relationship": "fetched_for",
            }
        )

    return new_nodes, new_edges


def _mock_match(
    final_effects: list[dict],
    value_pool: list[dict],
    opp_layer: int,
) -> tuple[list[dict], list[dict]]:
    """Mock matching — sector string matching with deterministic scoring."""
    opportunities = []
    new_edges = []

    def _score(sentiment: float, discount: float, agreement: float) -> float:
        return round(min(100.0, sentiment * 0.3 + discount * 0.3 + agreement * 0.4), 1)

    for val in value_pool:
        for effect in final_effects:
            text = (
                effect.get("content", "") + " " + effect.get("reasoning", "")
            ).lower()
            sector = val.get("sector", "").lower()
            if sector and sector in text:
                score = _score(70.0, val.get("discount_pct", 0), 75.0)
                if score >= 50:
                    oid = f"opp-{uuid4().hex[:8]}"
                    opportunities.append(
                        {
                            "id": oid,
                            "layer": opp_layer,
                            "type": "opportunity",
                            "content": f"{val.get('ticker', '?')} — {score}% conviction",
                            "reasoning": f"Matched via {sector} sector. Effect: {effect['content'][:50]}",
                            "sources": [],
                            "parents": [effect["id"]],
                            "selected": True,
                            "metadata": {**val, "convergence_score": score},
                        }
                    )
                    new_edges.append(
                        {
                            "source": effect["id"],
                            "target": oid,
                            "relationship": "matches",
                        }
                    )
                    break
    return opportunities, new_edges


async def think_effects(
    parent_nodes: list[dict],
    news_pool: list[dict],
    current_layer_nodes: list[dict],
    next_layer: int,
    existing_ids: set[str],
) -> tuple[list[dict], list[dict]]:
    """Produce effect nodes from parent context. Uses real agents if available."""
    if _use_real_agents():
        try:
            from src.agents.thinking_crew import think_effects as real_think

            log.info("Using real CrewAI agents for layer %d", next_layer)
            nodes, edges = real_think(current_layer_nodes, news_pool, next_layer)
            if nodes:  # Only use if agents produced results
                return nodes, edges
            log.warning("Real agents produced 0 nodes, falling back to mock")
        except Exception as e:
            log.error("Real agent failed, falling back to mock: %s", e)

    log.info("Using mock reasoning for layer %d", next_layer)
    return _mock_think_effects(
        parent_nodes, news_pool, current_layer_nodes, next_layer, existing_ids
    )


async def match_opportunities(
    final_effects: list[dict],
    value_pool: list[dict],
    opp_layer: int,
) -> tuple[list[dict], list[dict]]:
    """Match effects against value pool. Uses real agents if available."""
    if _use_real_agents():
        try:
            from src.agents.thinking_crew import match_opportunities as real_match

            log.info("Using real CrewAI agents for matching")
            opps, edges = real_match(final_effects, value_pool)
            if opps:
                return opps, edges
            log.warning("Real agent matching produced 0 results, falling back to mock")
        except Exception as e:
            log.error("Real agent matching failed, falling back to mock: %s", e)

    log.info("Using mock matching")
    return _mock_match(final_effects, value_pool, opp_layer)
