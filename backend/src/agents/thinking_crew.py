"""Three-agent thinking pipeline: Thinker, Matcher, Controller."""

import json
import logging
from uuid import uuid4

from crewai import Agent, Crew, Task

from src.agents.llm_config import get_main_llm
from src.agents.skills.base import build_system_prompt_with_skills
from src.agents.tools.fetch_news import FetchNewsTool
from src.agents.thinking_helpers import (
    CONFIDENCE_THRESHOLD,
    MATCHER_SKILLS,
    THINKER_SKILLS,
    convergence_score,
    parse_json_response,
    prepare_parent_nodes,
)

log = logging.getLogger("nexis.agents")

_parse_json_response = parse_json_response  # noqa: F841 — re-export
_prepare_parent_nodes = prepare_parent_nodes


def run_thinker(
    parent_nodes: list[dict],
    chain_summary: str,
    news_pool: list[dict],
    layer: int,
) -> tuple[list[dict], list[dict], list[dict], list[dict], int]:
    """Trace causal effects one layer deeper.

    Returns:
        (effect_nodes, fetch_nodes, effect_edges, fetch_edges, tokens)
    """
    if not parent_nodes:
        return [], [], [], [], 0

    try:
        system_prompt = build_system_prompt_with_skills(allowed_skills=THINKER_SKILLS)
        thinker = Agent(
            role="Financial Effects Analyst",
            goal="Identify causal market effects using your analytical skills",
            backstory=system_prompt,
            llm=get_main_llm(),
            tools=[FetchNewsTool()],
            verbose=False,
        )

        parents_json = json.dumps(
            _prepare_parent_nodes(parent_nodes, current_layer=layer),
            ensure_ascii=False,
        )

        pool_json = json.dumps(
            [
                {
                    "id": n.get("id", ""),
                    "title": n.get("title", n.get("summary", "")),
                    "summary": n.get("summary", ""),
                }
                for n in news_pool[:20]
            ],
            ensure_ascii=False,
        )

        chain_ctx = (
            f"Chain summary so far:\n{chain_summary}\n\n" if chain_summary else ""
        )

        think_task = Task(
            description=(
                f"{chain_ctx}"
                f"Analyze these financial events and identify their next-order "
                f"market effects.\n\n"
                f"Parent nodes (layers 0-{layer - 1}):\n{parents_json}\n\n"
                f"Available news pool:\n{pool_json}\n\n"
                f"For each effect:\n"
                f"1. Content — what happens\n"
                f"2. Reasoning — the causal chain from parent(s)\n"
                f"3. Confidence (0-100) — naturally lower for deeper chains\n"
                f"4. Parent IDs — which parent(s) cause it\n"
                f"5. Sector — affected sector\n"
                f"6. Fetched news IDs — any news from pool you reference\n"
                f"7. Information gaps — what you wish you knew\n\n"
                f"Return JSON:\n"
                f'{{"effects": [{{"content": str, "reasoning": str, '
                f'"confidence": int, "parent_ids": [str], "sector": str, '
                f'"fetched_news_ids": [str], "information_gaps": [str]}}]}}\n\n'
                f"Return ONLY valid JSON."
            ),
            expected_output="JSON object with 'effects' array.",
            agent=thinker,
        )

        crew = Crew(agents=[thinker], tasks=[think_task], verbose=False)
        result = crew.kickoff()

        tokens = (
            result.token_usage.total_tokens
            if hasattr(result, "token_usage") and result.token_usage
            else 0
        )

        raw = result.raw if hasattr(result, "raw") else str(result)
        parsed = parse_json_response(raw)
        if parsed is None:
            log.warning(
                "Thinker JSON parse failed at layer %d. Raw[0:500]: %s",
                layer,
                raw[:500],
            )
            return [], [], [], [], 0

        effect_nodes, fetch_nodes, effect_edges, fetch_edges = _build_thinker_output(
            parsed.get("effects", []), parent_nodes, news_pool, layer
        )
        return effect_nodes, fetch_nodes, effect_edges, fetch_edges, tokens

    except Exception as e:
        log.error("run_thinker failed at layer %d: %s", layer, e)
        return [], [], [], [], 0


def _build_thinker_output(
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

    log.info(
        "Thinker layer %d: %d effects, %d fetches from %d parents",
        layer,
        len(effect_nodes),
        len(fetch_nodes),
        len(parent_nodes),
    )
    return effect_nodes, fetch_nodes, effect_edges, fetch_edges


def run_matcher(
    effects: list[dict],
    value_pool: list[dict],
) -> tuple[list[dict], list[dict], int]:
    """Match effects against value stocks to find opportunities.

    Opportunities placed at same layer as parent effect.
    No ticker dedup — different causal paths are distinct opportunities.

    Returns:
        (opportunity_nodes, edges, tokens)
    """
    if not effects or not value_pool:
        return [], [], 0

    try:
        system_prompt = build_system_prompt_with_skills(allowed_skills=MATCHER_SKILLS)
        matcher = Agent(
            role="Value Opportunity Matcher",
            goal="Match market effects to undervalued stocks",
            backstory=system_prompt,
            llm=get_main_llm(),
            verbose=False,
        )

        effects_json = json.dumps(
            [
                {
                    "id": e.get("id", ""),
                    "content": e.get("content", ""),
                    "reasoning": e.get("reasoning", ""),
                    "confidence": e.get("confidence", 50),
                }
                for e in effects
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
                f"Match these market effects to value stocks that benefit.\n\n"
                f"Effects:\n{effects_json}\n\n"
                f"Value stocks:\n{values_json}\n\n"
                f"For each match:\n"
                f"1. Which effect benefits the stock (effect_id)\n"
                f"2. sentiment_score (0-100): how positive for this stock\n"
                f"3. agreement_score (0-100): confidence in this match\n"
                f"4. Reasoning\n\n"
                f"Return JSON:\n"
                f'{{"matches": [{{"ticker": str, "effect_id": str, '
                f'"sentiment_score": float, "agreement_score": float, '
                f'"reasoning": str}}]}}\n\n'
                f"Only include high-confidence matches. Return ONLY valid JSON."
            ),
            expected_output="JSON object with 'matches' array.",
            agent=matcher,
        )

        crew = Crew(agents=[matcher], tasks=[match_task], verbose=False)
        result = crew.kickoff()

        tokens = (
            result.token_usage.total_tokens
            if hasattr(result, "token_usage") and result.token_usage
            else 0
        )

        raw = result.raw if hasattr(result, "raw") else str(result)
        parsed = parse_json_response(raw)
        if parsed is None:
            log.warning("Matcher JSON parse failed")
            return [], [], 0

        opp_nodes, edges = _build_matcher_output(
            parsed.get("matches", []), effects, value_pool
        )
        return opp_nodes, edges, tokens

    except Exception as e:
        log.error("run_matcher failed: %s", e)
        return [], [], 0


def _build_matcher_output(
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

    log.info(
        "Matcher: %d opportunities from %d effects x %d values",
        len(opportunity_nodes),
        len(effects),
        len(value_pool),
    )
    return opportunity_nodes, new_edges


def run_controller(
    chain_summary: str,
    effects: list[dict],
    matches: list[dict],
    layer: int,
    max_depth: int,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> tuple[dict, int]:
    """Evaluate reasoning quality and decide whether to continue.

    Returns:
        ({"continue": bool, "reasoning": str, "summary": str}, tokens)
    """
    # Deterministic stops — no LLM needed
    if not effects:
        return {
            "continue": False,
            "reasoning": "No effects produced by thinker — nothing to explore.",
            "summary": chain_summary,
        }, 0

    avg_conf = sum(e.get("confidence", 0) for e in effects) / len(effects)

    if layer >= max_depth:
        return {
            "continue": False,
            "reasoning": f"Reached max depth ({max_depth}). Stopping.",
            "summary": chain_summary,
        }, 0

    if avg_conf < confidence_threshold:
        return {
            "continue": False,
            "reasoning": (
                f"Average confidence too low ({avg_conf:.0f} < "
                f"{confidence_threshold}). Further reasoning would be speculative."
            ),
            "summary": chain_summary,
        }, 0

    # LLM-based decision
    try:
        controller = Agent(
            role="Thinking Chain Evaluator",
            goal="Decide whether deeper causal reasoning is productive",
            backstory=(
                "You evaluate the quality and novelty of a multi-layer "
                "causal reasoning chain. Your job is to decide if exploring "
                "one layer deeper would yield valuable insights or if the "
                "chain has reached diminishing returns."
            ),
            llm=get_main_llm(),
            verbose=False,
        )

        effects_json = json.dumps(
            [
                {"content": e.get("content", ""), "confidence": e.get("confidence", 0)}
                for e in effects
            ],
            ensure_ascii=False,
        )

        match_count = len(matches)
        avg_score = (
            sum(m.get("convergence_score", 0) for m in matches) / match_count
            if match_count
            else 0
        )

        ctrl_task = Task(
            description=(
                f"Evaluate this thinking chain and decide: continue or stop?\n\n"
                f"Chain summary:\n{chain_summary}\n\n"
                f"This layer's effects ({len(effects)}):\n{effects_json}\n\n"
                f"Average confidence: {avg_conf:.0f}\n"
                f"Matches found: {match_count}"
                f"{f' (avg score: {avg_score:.0f})' if match_count else ''}\n"
                f"Current layer: {layer} / {max_depth}\n\n"
                f"Decide:\n"
                f"- continue=true if unexplored causal paths remain\n"
                f"- continue=false if chains are speculative or exhausted\n\n"
                f"Return JSON:\n"
                f'{{"continue": bool, "reasoning": str, "summary": str}}\n\n'
                f"The summary should narrate the full chain so far. "
                f"Return ONLY valid JSON."
            ),
            expected_output="JSON with continue, reasoning, summary.",
            agent=controller,
        )

        crew = Crew(agents=[controller], tasks=[ctrl_task], verbose=False)
        result = crew.kickoff()

        tokens = (
            result.token_usage.total_tokens
            if hasattr(result, "token_usage") and result.token_usage
            else 0
        )

        raw = result.raw if hasattr(result, "raw") else str(result)
        parsed = parse_json_response(raw)
        if parsed is None:
            log.warning("Controller JSON parse failed at layer %d", layer)
            return {
                "continue": False,
                "reasoning": "Error: failed to parse controller response.",
                "summary": chain_summary,
            }, 0

        return {
            "continue": bool(parsed.get("continue", False)),
            "reasoning": parsed.get("reasoning", ""),
            "summary": parsed.get("summary", chain_summary),
        }, tokens

    except Exception as e:
        log.error("run_controller failed at layer %d: %s", layer, e)
        return {
            "continue": False,
            "reasoning": f"Error in controller: {e}",
            "summary": chain_summary,
        }, 0
