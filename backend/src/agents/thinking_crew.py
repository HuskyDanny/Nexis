"""Three-agent thinking pipeline: Thinker, Matcher, Controller.

Each function creates a specialized CrewAI agent, kicks off a crew,
parses the JSON response, and constructs graph nodes/edges.
Re-exported from thinking_helpers: convergence_score(), _parse_json_response()
"""

import json
import os
import time
from uuid import uuid4

from crewai import Agent, Crew, Task

from src.agents.llm_config import get_main_llm
from src.agents.skills.base import build_system_prompt_with_skills
from src.agents.tools.fetch_news import FetchNewsTool
from src.agents.tools.graph_search import GraphSearchTool
from src.agents.tools.explore_entity import ExploreEntityTool
from src.agents.tools.find_paths import FindPathsTool
from src.agents.tools.get_relationships import GetRelationshipsTool
from src.agents.thinking_helpers import (
    CONFIDENCE_THRESHOLD,
    KNOWLEDGE_REUSE_SKILL,
    MATCHER_SKILLS,
    THINKER_SKILLS,
    convergence_score,
    parse_json_response,
    prepare_parent_nodes,
)
from src.agents.thinking_models import (  # noqa: E402
    ControllerOutput as ControllerOutputModel,
    MatcherOutput,
    ThinkerOutput,
)
from src.core.logger import get_logger

log = get_logger("agents")


def _is_debug() -> bool:
    """Check debug mode from LOG_LEVEL env var directly (avoids cached logger level)."""
    return os.environ.get("LOG_LEVEL", "").upper() == "DEBUG"


_parse_json_response = parse_json_response  # noqa: F841 — re-export


def build_thinker_prompt(
    parent_nodes: list[dict],
    chain_summary: str,
    news_pool: list[dict],
    layer: int,
) -> str:
    """Build the thinker agent prompt. Shared between CrewAI and direct LiteLLM paths."""
    parents_json = json.dumps(
        prepare_parent_nodes(parent_nodes, current_layer=layer),
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
    chain_ctx = f"Chain summary so far:\n{chain_summary}\n\n" if chain_summary else ""
    return (
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
    )


def run_thinker(
    parent_nodes: list[dict],
    chain_summary: str,
    news_pool: list[dict],
    layer: int,
    session_id: str = "",
) -> tuple[list[dict], list[dict], list[dict], list[dict], int]:
    """Trace causal effects one layer deeper.

    Returns (effect_nodes, fetch_nodes, effect_edges, fetch_edges, tokens).
    """
    if not parent_nodes:
        return [], [], [], [], 0

    tokens = 0
    try:
        system_prompt = (
            build_system_prompt_with_skills(allowed_skills=THINKER_SKILLS)
            + "\n\n"
            + KNOWLEDGE_REUSE_SKILL
        )
        # Build tool list — graph tools (free, fast) alongside fetch_news
        try:
            from src.graph.dependencies import get_graph_store

            graph_store = get_graph_store()
            tools = [
                GraphSearchTool(graph_store=graph_store),
                ExploreEntityTool(graph_store=graph_store),
                FindPathsTool(graph_store=graph_store),
                GetRelationshipsTool(graph_store=graph_store),
                FetchNewsTool(),
            ]
        except (RuntimeError, ImportError):
            tools = [FetchNewsTool()]  # Graph not initialized, fallback
        thinker = Agent(
            role="Financial Effects Analyst",
            goal="Identify causal market effects using your analytical skills",
            backstory=system_prompt,
            llm=get_main_llm(),
            tools=tools,
            verbose=_is_debug(),
        )

        description = build_thinker_prompt(
            parent_nodes=parent_nodes,
            chain_summary=chain_summary,
            news_pool=news_pool,
            layer=layer,
        )
        prompt_chars = len(description)
        if _is_debug():
            log.debug("THINKER L%d prompt: %s", layer, description[:500])
        think_task = Task(
            description=description,
            expected_output="JSON object with 'effects' array.",
            agent=thinker,
            output_json=ThinkerOutput,
        )

        crew = Crew(agents=[thinker], tasks=[think_task], verbose=_is_debug())
        t0 = time.perf_counter()
        result = crew.kickoff()
        elapsed = time.perf_counter() - t0

        tokens = getattr(getattr(result, "token_usage", None), "total_tokens", 0) or 0

        # Prefer structured output_json; fall back to raw parsing
        parsed = getattr(result, "json_dict", None)
        if not parsed:
            raw = getattr(result, "raw", None)
            if raw is None:
                raw = str(result)
            if _is_debug():
                log.debug("THINKER L%d raw response: %s", layer, raw[:1000])
            parsed = parse_json_response(raw)
        if not isinstance(parsed, dict):
            log.warning("Thinker JSON parse failed at layer %d", layer)
            return [], [], [], [], tokens

        n_effects = len(parsed.get("effects", []))
        effect_nodes, fetch_nodes, effect_edges, fetch_edges = _build_thinker_output(
            parsed.get("effects", []), parent_nodes, news_pool, layer
        )
        n_fetch = len(fetch_nodes)
        log.info(
            "THINKER L%d | skills=%d | %.1fs | parsed=%d effects, %d fetch | prompt=%d chars | tokens=%d",
            layer,
            len(THINKER_SKILLS),
            elapsed,
            n_effects,
            n_fetch,
            prompt_chars,
            tokens,
        )
        return effect_nodes, fetch_nodes, effect_edges, fetch_edges, tokens

    except Exception as e:
        label = (
            "expected"
            if isinstance(e, (json.JSONDecodeError, ValueError, KeyError, RuntimeError))
            else "unexpected"
        )
        log.error(
            "run_thinker %s error at layer %d (%s): %s",
            label,
            layer,
            type(e).__name__,
            e,
        )
        return [], [], [], [], tokens


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


def run_matcher(
    effects: list[dict],
    value_pool: list[dict],
) -> tuple[list[dict], list[dict], int]:
    """Match effects to value stocks. Returns (opportunity_nodes, edges, tokens)."""
    if not effects or not value_pool:
        return [], [], 0

    tokens = 0
    try:
        system_prompt = build_system_prompt_with_skills(allowed_skills=MATCHER_SKILLS)
        matcher = Agent(
            role="Value Opportunity Matcher",
            goal="Match market effects to undervalued stocks",
            backstory=system_prompt,
            llm=get_main_llm(),
            verbose=_is_debug(),
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
        description = (
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
        )
        prompt_chars = len(description)
        if _is_debug():
            log.debug("MATCHER prompt: %s", description[:500])
        match_task = Task(
            description=description,
            expected_output="JSON object with 'matches' array.",
            agent=matcher,
            output_json=MatcherOutput,
        )

        crew = Crew(agents=[matcher], tasks=[match_task], verbose=_is_debug())
        t0 = time.perf_counter()
        result = crew.kickoff()
        elapsed = time.perf_counter() - t0

        tokens = getattr(getattr(result, "token_usage", None), "total_tokens", 0) or 0

        # Prefer structured output_json; fall back to raw parsing
        parsed = getattr(result, "json_dict", None)
        if not parsed:
            raw = getattr(result, "raw", None)
            if raw is None:
                raw = str(result)
            if _is_debug():
                log.debug("MATCHER raw response: %s", raw[:1000])
            parsed = parse_json_response(raw)
        if not isinstance(parsed, dict):
            log.warning("Matcher JSON parse failed")
            return [], [], tokens

        n_parsed = len(parsed.get("matches", []))
        opp_nodes, edges = _build_matcher_output(
            parsed.get("matches", []), effects, value_pool
        )
        n_built = len(opp_nodes)
        log.info(
            "MATCHER | skills=%d | %.1fs | parsed=%d, built=%d opportunities | prompt=%d chars | tokens=%d",
            len(MATCHER_SKILLS),
            elapsed,
            n_parsed,
            n_built,
            prompt_chars,
            tokens,
        )
        return opp_nodes, edges, tokens

    except Exception as e:
        label = (
            "expected"
            if isinstance(e, (json.JSONDecodeError, ValueError, KeyError, RuntimeError))
            else "unexpected"
        )
        log.error("run_matcher %s error (%s): %s", label, type(e).__name__, e)
        return [], [], tokens


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
                "content": f"{ticker} — {score}% conviction",
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


def run_controller(
    chain_summary: str,
    effects: list[dict],
    matches: list[dict],
    layer: int,
    max_depth: int,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> tuple[dict, int]:
    """Evaluate reasoning quality and decide whether to continue.

    Returns ({"continue": bool, "reasoning": str, "summary": str}, tokens).
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
    tokens = 0
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
            verbose=_is_debug(),
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
        description = (
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
        )
        prompt_chars = len(description)
        if _is_debug():
            log.debug("CONTROLLER L%d prompt: %s", layer, description[:500])
        ctrl_task = Task(
            description=description,
            expected_output="JSON with continue, reasoning, summary.",
            agent=controller,
            output_json=ControllerOutputModel,
        )

        crew = Crew(agents=[controller], tasks=[ctrl_task], verbose=_is_debug())
        t0 = time.perf_counter()
        result = crew.kickoff()
        elapsed = time.perf_counter() - t0

        tokens = getattr(getattr(result, "token_usage", None), "total_tokens", 0) or 0

        # Prefer structured output_json; fall back to raw parsing
        parsed = getattr(result, "json_dict", None)
        if not parsed:
            raw = getattr(result, "raw", None)
            if raw is None:
                raw = str(result)
            if _is_debug():
                log.debug("CONTROLLER L%d raw response: %s", layer, raw[:1000])
            parsed = parse_json_response(raw)
        if not isinstance(parsed, dict):
            log.warning("Controller JSON parse failed at layer %d", layer)
            return {
                "continue": False,
                "reasoning": "Error: failed to parse controller response.",
                "summary": chain_summary,
            }, tokens

        ctrl_result = {
            "continue": bool(
                parsed.get("continue", parsed.get("continue_decision", False))
            ),
            "reasoning": parsed.get("reasoning", ""),
            "summary": parsed.get("summary", chain_summary),
        }
        _s = (
            str(ctrl_result["summary"])
            .replace("\n", " ")
            .replace("\r", " ")
            .replace('"', '\\"')[:80]
        )
        log.info(
            'CONTROLLER L%d | %.1fs | continue=%s | prompt=%d chars | tokens=%d | summary="%s"',
            layer,
            elapsed,
            ctrl_result["continue"],
            prompt_chars,
            tokens,
            _s,
        )
        return ctrl_result, tokens

    except Exception as e:
        label = (
            "expected"
            if isinstance(e, (json.JSONDecodeError, ValueError, KeyError, RuntimeError))
            else "unexpected"
        )
        log.error(
            "run_controller %s error at layer %d (%s): %s",
            label,
            layer,
            type(e).__name__,
            e,
        )
        return {
            "continue": False,
            "reasoning": f"Error in controller: {e}",
            "summary": chain_summary,
        }, tokens
