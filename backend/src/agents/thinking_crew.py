"""Three-agent thinking pipeline: Thinker, Matcher, Controller.

Public API: run_thinker(), run_matcher(), run_controller().
Re-exports: convergence_score(), _parse_json_response().
"""

import json
import logging
import time

from crewai import Agent, Crew, Task

from src.agents.llm_config import get_main_llm
from src.agents.skills.base import build_system_prompt_with_skills
from src.agents.tools.fetch_news import FetchNewsTool
from src.core.logger import get_logger
from src.agents.thinking_helpers import (
    CONFIDENCE_THRESHOLD,
    MATCHER_SKILLS,
    THINKER_SKILLS,
    build_matcher_output,
    build_thinker_output,
    convergence_score,
    parse_json_response,
    prepare_parent_nodes,
)

log = get_logger("agents")


def _is_debug() -> bool:
    """Check if logger is in DEBUG mode."""
    return log.isEnabledFor(logging.DEBUG)


# Re-export for backward compat and test access
_parse_json_response = parse_json_response  # noqa: F841
_prepare_parent_nodes = prepare_parent_nodes


def run_thinker(
    parent_nodes: list[dict],
    chain_summary: str,
    news_pool: list[dict],
    layer: int,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Trace causal effects one layer deeper.

    Returns:
        (effect_nodes, fetch_nodes, effect_edges, fetch_edges)
    """
    if not parent_nodes:
        return [], [], [], []

    try:
        debug = _is_debug()
        system_prompt = build_system_prompt_with_skills(allowed_skills=THINKER_SKILLS)
        thinker = Agent(
            role="Financial Effects Analyst",
            goal="Identify causal market effects using your analytical skills",
            backstory=system_prompt,
            llm=get_main_llm(),
            tools=[FetchNewsTool()],
            verbose=debug,
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

        prompt_desc = (
            f"{chain_ctx}"
            f"Analyze these financial events and identify their next-order "
            f"market effects.\n\n"
            f"Parent nodes (layers 0-{layer - 1}):\n{parents_json}\n\n"
            f"Available news pool:\n{pool_json}\n\n"
            f"For each effect:\n"
            f"1. Content \u2014 what happens\n"
            f"2. Reasoning \u2014 the causal chain from parent(s)\n"
            f"3. Confidence (0-100) \u2014 naturally lower for deeper chains\n"
            f"4. Parent IDs \u2014 which parent(s) cause it\n"
            f"5. Sector \u2014 affected sector\n"
            f"6. Fetched news IDs \u2014 any news from pool you reference\n"
            f"7. Information gaps \u2014 what you wish you knew\n\n"
            f"Return JSON:\n"
            f'{{"effects": [{{"content": str, "reasoning": str, '
            f'"confidence": int, "parent_ids": [str], "sector": str, '
            f'"fetched_news_ids": [str], "information_gaps": [str]}}]}}\n\n'
            f"Return ONLY valid JSON."
        )

        think_task = Task(
            description=prompt_desc,
            expected_output="JSON object with 'effects' array.",
            agent=thinker,
        )

        crew = Crew(agents=[thinker], tasks=[think_task], verbose=debug)
        if _is_debug():
            log.debug(
                "THINKER L%d prompt (%d chars): %s",
                layer,
                len(prompt_desc),
                prompt_desc[:500] if len(prompt_desc) > 500 else prompt_desc,
            )
        t0 = time.perf_counter()
        result = crew.kickoff()
        elapsed = time.perf_counter() - t0

        raw = result.raw if hasattr(result, "raw") else str(result)
        log.debug("THINKER L%d raw response: %s", layer, raw)
        parsed = parse_json_response(raw)
        if parsed is None:
            log.warning(
                "Thinker JSON parse failed at layer %d. Raw[0:500]: %s",
                layer,
                raw[:500],
            )
            return [], [], [], []

        effects = parsed.get("effects", [])
        fetch_count = sum(len(e.get("fetched_news_ids", [])) for e in effects)
        log.info(
            "THINKER L%d | skills=%d | %.1fs | parsed=%d effects, %d fetch | prompt=%d chars",
            layer,
            len(THINKER_SKILLS),
            elapsed,
            len(effects),
            fetch_count,
            len(prompt_desc),
        )

        return build_thinker_output(effects, parent_nodes, news_pool, layer)

    except Exception:
        log.exception("run_thinker failed at layer %d", layer)
        return [], [], [], []


def run_matcher(
    effects: list[dict],
    value_pool: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Match effects against value stocks to find opportunities.

    Opportunities placed at same layer as parent effect.
    No ticker dedup \u2014 different causal paths are distinct opportunities.

    Returns:
        (opportunity_nodes, edges)
    """
    if not effects or not value_pool:
        return [], []

    try:
        debug = _is_debug()
        system_prompt = build_system_prompt_with_skills(allowed_skills=MATCHER_SKILLS)
        matcher = Agent(
            role="Value Opportunity Matcher",
            goal="Match market effects to undervalued stocks",
            backstory=system_prompt,
            llm=get_main_llm(),
            verbose=debug,
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

        prompt_desc = (
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

        match_task = Task(
            description=prompt_desc,
            expected_output="JSON object with 'matches' array.",
            agent=matcher,
        )

        crew = Crew(agents=[matcher], tasks=[match_task], verbose=debug)
        t0 = time.perf_counter()
        result = crew.kickoff()
        elapsed = time.perf_counter() - t0

        raw = result.raw if hasattr(result, "raw") else str(result)
        log.debug("MATCHER raw response: %s", raw)
        parsed = parse_json_response(raw)
        if parsed is None:
            log.warning("Matcher JSON parse failed")
            return [], []

        matches = parsed.get("matches", [])
        log.info(
            "MATCHER | skills=%d | %.1fs | parsed=%d opportunities | prompt=%d chars",
            len(MATCHER_SKILLS),
            elapsed,
            len(matches),
            len(prompt_desc),
        )
        return build_matcher_output(matches, effects, value_pool)

    except Exception:
        log.exception("run_matcher failed")
        return [], []


def run_controller(
    chain_summary: str,
    effects: list[dict],
    matches: list[dict],
    layer: int,
    max_depth: int,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> dict:
    """Evaluate reasoning quality and decide whether to continue.

    Returns:
        {"continue": bool, "reasoning": str, "summary": str}
    """
    # Deterministic stops \u2014 no LLM needed
    if not effects:
        return {
            "continue": False,
            "reasoning": "No effects produced by thinker \u2014 nothing to explore.",
            "summary": chain_summary,
        }

    avg_conf = sum(e.get("confidence", 0) for e in effects) / len(effects)

    if layer >= max_depth:
        return {
            "continue": False,
            "reasoning": f"Reached max depth ({max_depth}). Stopping.",
            "summary": chain_summary,
        }

    if avg_conf < confidence_threshold:
        return {
            "continue": False,
            "reasoning": (
                f"Average confidence too low ({avg_conf:.0f} < "
                f"{confidence_threshold}). Further reasoning would be speculative."
            ),
            "summary": chain_summary,
        }

    # LLM-based decision
    try:
        debug = _is_debug()
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
            verbose=debug,
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

        prompt_desc = (
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

        ctrl_task = Task(
            description=prompt_desc,
            expected_output="JSON with continue, reasoning, summary.",
            agent=controller,
        )

        crew = Crew(agents=[controller], tasks=[ctrl_task], verbose=debug)
        t0 = time.perf_counter()
        result = crew.kickoff()
        elapsed = time.perf_counter() - t0

        raw = result.raw if hasattr(result, "raw") else str(result)
        log.debug("CONTROLLER L%d raw response: %s", layer, raw)
        parsed = parse_json_response(raw)
        if parsed is None:
            log.warning("Controller JSON parse failed at layer %d", layer)
            return {
                "continue": False,
                "reasoning": "Error: failed to parse controller response.",
                "summary": chain_summary,
            }

        decision = bool(parsed.get("continue", False))
        log.info(
            "CONTROLLER L%d | %.1fs | continue=%s | prompt=%d chars",
            layer,
            elapsed,
            decision,
            len(prompt_desc),
        )

        return {
            "continue": decision,
            "reasoning": parsed.get("reasoning", ""),
            "summary": parsed.get("summary", chain_summary),
        }

    except Exception:
        log.exception("run_controller failed at layer %d", layer)
        return {
            "continue": False,
            "reasoning": "Error in controller — see logs for traceback.",
            "summary": chain_summary,
        }
