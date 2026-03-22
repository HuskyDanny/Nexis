"""CrewAI agent definitions for the Financial Agent v2 thinking pipeline.

Three crew functions that correspond to pipeline stages:
1. rank_and_select_news — rank news by market impact (small LLM)
2. think_effects — reason about causal effects from parent nodes (main LLM)
3. match_opportunities — match effects against value stocks (main LLM)
"""

import json
import logging
from uuid import uuid4

from crewai import Agent, Crew, Task

from src.agents.llm_config import get_main_llm, get_small_llm
from src.agents.skills.base import load_skill, build_system_prompt

log = logging.getLogger("fa2.agents")


def convergence_score(sentiment: float, discount: float, agreement: float) -> float:
    """Deterministic convergence score: sentiment*0.3 + discount*0.3 + agreement*0.4."""
    return round(min(100.0, sentiment * 0.3 + discount * 0.3 + agreement * 0.4), 1)


def rank_and_select_news(news_pool: list[dict]) -> list[dict]:
    """Use small LLM to rank news items by market impact.

    Returns news items sorted by impact score (highest first).
    Falls back to returning all news unchanged if LLM fails.
    """
    if not news_pool:
        return []

    try:
        ranker = Agent(
            role="News Impact Ranker",
            goal="Rank financial news items by their potential market impact",
            backstory=(
                "You are a senior financial analyst who specializes in quickly "
                "assessing which news headlines will move markets the most."
            ),
            llm=get_small_llm(),
            verbose=False,
        )

        news_summary = json.dumps(
            [
                {"id": n.get("id", ""), "title": n.get("title", n.get("summary", ""))}
                for n in news_pool
            ],
            ensure_ascii=False,
        )

        rank_task = Task(
            description=(
                f"Rank the following news items by potential market impact (high to low). "
                f"Return a JSON array of objects with 'id' and 'impact_score' (0-100).\n\n"
                f"News items:\n{news_summary}\n\n"
                f"Return ONLY valid JSON, no explanation."
            ),
            expected_output="A JSON array of {id, impact_score} sorted by impact_score descending.",
            agent=ranker,
        )

        crew = Crew(agents=[ranker], tasks=[rank_task], verbose=False)
        result = crew.kickoff()

        # Parse LLM response
        raw = result.raw if hasattr(result, "raw") else str(result)
        # Extract JSON from response (handle markdown code blocks)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        ranked = json.loads(raw.strip())

        # Build id -> score map
        score_map = {item["id"]: item.get("impact_score", 50) for item in ranked}

        # Sort news pool by score
        sorted_news = sorted(
            news_pool,
            key=lambda n: score_map.get(n.get("id", ""), 50),
            reverse=True,
        )
        log.info("Ranked %d news items by impact", len(sorted_news))
        return sorted_news

    except Exception as e:
        log.warning("News ranking failed, returning all news unsorted: %s", e)
        return list(news_pool)


def think_effects(
    parent_nodes: list[dict], news_pool: list[dict], layer: int
) -> tuple[list[dict], list[dict]]:
    """Use main LLM to reason about causal effects of parent nodes.

    Args:
        parent_nodes: Selected nodes from the current layer to reason about.
        news_pool: Full news pool the agent can reference for additional context.
        layer: The target layer number for new effect nodes.

    Returns:
        (new_nodes, new_edges) matching ThinkingNode/ThinkingEdge schema.
    """
    if not parent_nodes:
        return [], []

    try:
        system_prompt = build_system_prompt()
        thinker = Agent(
            role="Financial Effects Analyst",
            goal="Identify causal market effects from financial events using your analytical skills",
            backstory=system_prompt,
            llm=get_main_llm(),
            tools=[load_skill],
            verbose=False,
        )

        parents_json = json.dumps(
            [
                {
                    "id": n.get("id", ""),
                    "content": n.get("content", ""),
                    "type": n.get("type", ""),
                    "metadata": n.get("metadata", {}),
                }
                for n in parent_nodes
            ],
            ensure_ascii=False,
        )

        pool_json = json.dumps(
            [
                {"id": n.get("id", ""), "title": n.get("title", n.get("summary", ""))}
                for n in news_pool[:20]  # limit context size
            ],
            ensure_ascii=False,
        )

        existing_ids = {n.get("id", "") for n in parent_nodes}

        think_task = Task(
            description=(
                f"Analyze these financial events and identify their market effects.\n\n"
                f"Parent nodes (layer {layer - 1}):\n{parents_json}\n\n"
                f"Available news pool (you may reference relevant items):\n{pool_json}\n\n"
                f"For each effect you identify:\n"
                f"1. Explain the causal chain (reasoning)\n"
                f"2. List which parent node(s) cause it (parent_ids)\n"
                f"3. Note if you used any news from the pool (fetched_news_ids)\n"
                f"4. Identify the affected sector\n\n"
                f"Return a JSON object with:\n"
                f"- 'effects': array of {{'content': str, 'reasoning': str, "
                f"'parent_ids': [str], 'sector': str, 'fetched_news_ids': [str]}}\n\n"
                f"Return ONLY valid JSON."
            ),
            expected_output="JSON object with 'effects' array.",
            agent=thinker,
        )

        crew = Crew(agents=[thinker], tasks=[think_task], verbose=False)
        result = crew.kickoff()

        raw = result.raw if hasattr(result, "raw") else str(result)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())

        effects = parsed.get("effects", [])
        new_nodes: list[dict] = []
        new_edges: list[dict] = []

        for effect in effects:
            effect_id = uuid4().hex[:12]
            parent_ids = [
                pid for pid in effect.get("parent_ids", []) if pid in existing_ids
            ]
            if not parent_ids:
                # Default to first parent if LLM didn't specify valid parents
                parent_ids = [parent_nodes[0]["id"]]

            new_nodes.append(
                {
                    "id": effect_id,
                    "layer": layer,
                    "type": "effect",
                    "content": effect.get("content", "Unknown effect"),
                    "reasoning": effect.get("reasoning", ""),
                    "sources": [],
                    "parents": parent_ids,
                    "selected": True,
                    "metadata": {
                        "sector": effect.get("sector", "general"),
                        "parent_count": len(parent_ids),
                    },
                }
            )

            for pid in parent_ids:
                new_edges.append(
                    {
                        "source": pid,
                        "target": effect_id,
                        "relationship": "causes" if layer == 1 else "compounds",
                    }
                )

            # Handle fetched news references
            for fetched_id in effect.get("fetched_news_ids", []):
                if fetched_id in existing_ids:
                    continue  # already in the graph
                # Find the news item in the pool
                fetched_item = next(
                    (n for n in news_pool if n.get("id") == fetched_id), None
                )
                if fetched_item:
                    fetch_node_id = f"fetch-{uuid4().hex[:8]}"
                    new_nodes.append(
                        {
                            "id": fetch_node_id,
                            "layer": layer,
                            "type": "fetch",
                            "content": f"Related: {fetched_item.get('title', fetched_item.get('summary', ''))}",
                            "reasoning": "Agent fetched this related news for additional context",
                            "sources": [fetched_item.get("url", "")],
                            "parents": [parent_ids[0]],
                            "selected": True,
                            "metadata": fetched_item,
                        }
                    )
                    new_edges.append(
                        {
                            "source": parent_ids[0],
                            "target": fetch_node_id,
                            "relationship": "fetched_for",
                        }
                    )
                    existing_ids.add(fetched_id)

        log.info(
            "Think layer %d: %d effects, %d edges from %d parents",
            layer,
            len(new_nodes),
            len(new_edges),
            len(parent_nodes),
        )
        return new_nodes, new_edges

    except Exception as e:
        log.error("Think effects failed at layer %d: %s", layer, e)
        return [], []


def match_opportunities(
    final_effects: list[dict], value_pool: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Use main LLM to match effects against value stocks.

    Args:
        final_effects: Selected effect nodes from the final thinking layer.
        value_pool: Value stocks to match against.

    Returns:
        (opportunity_nodes, edges) matching ThinkingNode/ThinkingEdge schema.
        convergence_score is computed deterministically, not by LLM.
    """
    if not final_effects or not value_pool:
        return [], []

    try:
        system_prompt = build_system_prompt()
        matcher = Agent(
            role="Value Opportunity Matcher",
            goal="Match market effects to undervalued stocks using your analytical skills",
            backstory=system_prompt,
            llm=get_main_llm(),
            tools=[load_skill],
            verbose=False,
        )

        effects_json = json.dumps(
            [
                {
                    "id": e.get("id", ""),
                    "content": e.get("content", ""),
                    "reasoning": e.get("reasoning", ""),
                    "metadata": e.get("metadata", {}),
                }
                for e in final_effects
            ],
            ensure_ascii=False,
        )

        values_json = json.dumps(
            [
                {
                    "ticker": v.get("ticker", ""),
                    "sector": v.get("sector", ""),
                    "discount_pct": v.get("discount_pct", 0),
                    "summary": v.get("summary", v.get("name", "")),
                }
                for v in value_pool
            ],
            ensure_ascii=False,
        )

        match_task = Task(
            description=(
                f"Match these market effects to value stocks that would benefit.\n\n"
                f"Effects:\n{effects_json}\n\n"
                f"Value stocks:\n{values_json}\n\n"
                f"For each match:\n"
                f"1. Identify which effect(s) benefit the stock\n"
                f"2. Rate sentiment_score (0-100): how positive is the effect for this stock\n"
                f"3. Rate agreement_score (0-100): how confident are you in this match\n"
                f"4. Explain the reasoning\n\n"
                f"Return a JSON object with:\n"
                f"- 'matches': array of {{'ticker': str, 'effect_id': str, "
                f"'sentiment_score': float, 'agreement_score': float, 'reasoning': str}}\n\n"
                f"Only include high-confidence matches. Return ONLY valid JSON."
            ),
            expected_output="JSON object with 'matches' array.",
            agent=matcher,
        )

        crew = Crew(agents=[matcher], tasks=[match_task], verbose=False)
        result = crew.kickoff()

        raw = result.raw if hasattr(result, "raw") else str(result)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())

        matches = parsed.get("matches", [])
        effect_map = {e.get("id", ""): e for e in final_effects}
        value_map = {v.get("ticker", ""): v for v in value_pool}

        # Determine the opportunity layer
        max_effect_layer = max((e.get("layer", 0) for e in final_effects), default=0)
        opp_layer = max_effect_layer + 1

        opportunity_nodes: list[dict] = []
        new_edges: list[dict] = []
        seen_tickers: set[str] = set()

        for match in matches:
            ticker = match.get("ticker", "")
            effect_id = match.get("effect_id", "")

            if ticker in seen_tickers:
                continue
            if effect_id not in effect_map:
                continue

            val = value_map.get(ticker, {})
            if not val:
                continue

            seen_tickers.add(ticker)

            # Deterministic convergence score
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
                {
                    "source": effect_id,
                    "target": opp_id,
                    "relationship": "matches",
                }
            )

        log.info(
            "Matched %d opportunities from %d effects x %d values",
            len(opportunity_nodes),
            len(final_effects),
            len(value_pool),
        )
        return opportunity_nodes, new_edges

    except Exception as e:
        log.error("Match opportunities failed: %s", e)
        return [], []
