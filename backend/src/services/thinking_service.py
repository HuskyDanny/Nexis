"""Thinking service — pipeline orchestrator.

Orchestrates the three-agent thinking pipeline:
- run_layer()    — one layer: Thinker -> Matcher -> Controller
- run_pipeline() — full loop until Controller stops or max_depth

No mock fallback. If LLM is down, pipeline returns empty/partial results.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

from src.agents.thinking_crew import run_controller, run_matcher, run_thinker
from src.core.logger import get_logger

log = get_logger("thinking.service")

AGENT_TIMEOUT_S = 60
AGENT_RETRIES = 1
DEFAULT_STOP_LAYER = 3


@dataclass
class LayerResult:
    """Result of a single pipeline layer."""

    effect_nodes: list[dict] = field(default_factory=list)
    fetch_nodes: list[dict] = field(default_factory=list)
    opportunity_nodes: list[dict] = field(default_factory=list)
    all_edges: list[dict] = field(default_factory=list)
    controller_decision: dict = field(
        default_factory=lambda: {"continue": False, "reasoning": "", "summary": ""}
    )


def _empty_layer_result(reason: str) -> LayerResult:
    """Return an empty LayerResult that signals stop."""
    return LayerResult(
        controller_decision={
            "continue": False,
            "reasoning": reason,
            "summary": "",
        }
    )


async def _call_with_retry(func, *args, **kwargs):
    """Call a sync function in an executor with timeout and 1 retry."""
    loop = asyncio.get_running_loop()
    last_err = None
    for attempt in range(1 + AGENT_RETRIES):
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                timeout=AGENT_TIMEOUT_S,
            )
            return result
        except Exception as e:
            last_err = e
            if attempt < AGENT_RETRIES:
                log.warning(
                    "Agent call failed (attempt %d), retrying: %s", attempt + 1, e
                )
    raise last_err  # type: ignore[misc]


async def run_layer(
    chain_summary: str,
    parent_nodes: list[dict],
    news_pool: list[dict],
    value_pool: list[dict],
    layer: int,
    max_depth: int,
    confidence_threshold: float = 35,
) -> LayerResult:
    """Run one layer of the pipeline: Thinker -> Matcher -> Controller.

    - Thinker fails -> empty LayerResult with continue=False
    - Matcher fails -> no matches this layer, continue
    - Controller fails -> default: continue if layer < 3, stop if >= 3
    """
    # --- Thinker ---
    try:
        effect_nodes, fetch_nodes, effect_edges, fetch_edges = await _call_with_retry(
            run_thinker,
            parent_nodes=parent_nodes,
            chain_summary=chain_summary,
            news_pool=news_pool,
            layer=layer,
        )
    except Exception as e:
        log.error("Thinker failed at layer %d: %s", layer, e)
        return _empty_layer_result(f"Thinker failed: {e}")

    if not effect_nodes:
        log.info("Thinker produced no effects at layer %d", layer)
        return _empty_layer_result("Thinker produced no effects")

    all_edges = list(effect_edges) + list(fetch_edges)

    # --- Matcher ---
    opportunity_nodes: list[dict] = []
    try:
        opportunity_nodes, match_edges = await _call_with_retry(
            run_matcher,
            effects=effect_nodes,
            value_pool=value_pool,
        )
        all_edges.extend(match_edges)
    except Exception as e:
        log.warning(
            "Matcher failed at layer %d, continuing without matches: %s", layer, e
        )

    # --- Controller ---
    try:
        ctrl = await _call_with_retry(
            run_controller,
            chain_summary=chain_summary,
            effects=effect_nodes,
            matches=opportunity_nodes,
            layer=layer,
            max_depth=max_depth,
            confidence_threshold=confidence_threshold,
        )
    except Exception as e:
        log.warning("Controller failed at layer %d, using default logic: %s", layer, e)
        should_continue = layer < DEFAULT_STOP_LAYER
        ctrl = {
            "continue": should_continue,
            "reasoning": f"Controller failed, default: {'continue' if should_continue else 'stop'}",
            "summary": chain_summary,
        }

    return LayerResult(
        effect_nodes=effect_nodes,
        fetch_nodes=fetch_nodes,
        opportunity_nodes=opportunity_nodes,
        all_edges=all_edges,
        controller_decision=ctrl,
    )


async def run_pipeline(
    session_id: str,
    seeds: list[dict],
    news_pool: list[dict],
    value_pool: list[dict],
    max_depth: int,
    on_layer_complete: Callable,
) -> None:
    """Run the full thinking pipeline loop.

    Iterates layers starting from 1. Each layer:
    1. Collects all selected nodes from prior layers as parent_nodes
    2. Calls run_layer()
    3. Persists via on_layer_complete callback
    4. Stops on: controller stop, max_depth reached, or empty effects
    """
    chain_summary = ""
    all_layer_nodes: list[list[dict]] = [seeds]  # layer 0 = seeds

    for layer in range(1, max_depth + 1):
        # Parent nodes: all selected nodes from prior layers
        parent_nodes = []
        for layer_nodes in all_layer_nodes:
            parent_nodes.extend(n for n in layer_nodes if n.get("selected", False))

        result = await run_layer(
            chain_summary=chain_summary,
            parent_nodes=parent_nodes,
            news_pool=news_pool,
            value_pool=value_pool,
            layer=layer,
            max_depth=max_depth,
        )

        await on_layer_complete(layer, result)

        # Accumulate this layer's nodes for future parent collection
        this_layer_nodes = (
            result.effect_nodes + result.fetch_nodes + result.opportunity_nodes
        )
        all_layer_nodes.append(this_layer_nodes)

        # Update chain summary from controller
        chain_summary = result.controller_decision.get("summary", chain_summary)

        # Termination: controller says stop or no effects produced
        if not result.controller_decision.get("continue", False):
            log.info(
                "Pipeline stopping at layer %d: %s",
                layer,
                result.controller_decision.get("reasoning", "unknown"),
            )
            break

    log.info(
        "Pipeline complete for session %s (%d layers)",
        session_id,
        len(all_layer_nodes) - 1,
    )
