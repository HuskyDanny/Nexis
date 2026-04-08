"""Thinking service — three-agent pipeline orchestrator (Thinker->Matcher->Controller)."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

from src.agents.llm_config import get_litellm_params
from src.agents.skills.base import build_system_prompt_with_skills
from src.agents.thinking_crew import (
    _build_thinker_output,
    build_thinker_prompt,
    run_controller,
    run_matcher,
    run_thinker,
)
from src.agents.thinking_helpers import THINKER_SKILLS, parse_json_response
from src.core.logger import get_logger
from src.services.session_events import SSEEvent, SessionRegistry
from src.services.stream_parser import IncrementalEffectsParser

# Alias for mockability in tests
try:
    from litellm import acompletion as litellm_acompletion
except ImportError:
    litellm_acompletion = None  # type: ignore

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
    tokens_used: dict[str, int] = field(default_factory=dict)


def _empty_layer_result(
    reason: str, tokens_used: Optional[dict[str, int]] = None
) -> LayerResult:
    """Return an empty LayerResult that signals stop."""
    return LayerResult(
        controller_decision={
            "continue": False,
            "reasoning": reason,
            "summary": "",
        },
        tokens_used=tokens_used if tokens_used is not None else {},
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
    session_id: str,
    confidence_threshold: float = 35,
) -> LayerResult:
    """Run one layer of the pipeline: Thinker -> Matcher -> Controller.

    - Thinker fails -> empty LayerResult with continue=False
    - Matcher fails -> no matches this layer, continue
    - Controller fails -> default: continue if layer < 3, stop if >= 3
    """
    # --- Thinker ---
    thinker_tokens = 0
    try:
        effect_nodes, fetch_nodes, effect_edges, fetch_edges, thinker_tokens = (
            await _call_with_retry(
                run_thinker,
                parent_nodes=parent_nodes,
                chain_summary=chain_summary,
                news_pool=news_pool,
                layer=layer,
                session_id=session_id,
            )
        )
    except Exception as e:
        log.error("Thinker failed at layer %d: %s", layer, e)
        return _empty_layer_result(f"Thinker failed: {e}", {"thinker": thinker_tokens})

    if not effect_nodes:
        log.info("Thinker produced no effects at layer %d", layer)
        return _empty_layer_result(
            "Thinker produced no effects", {"thinker": thinker_tokens}
        )

    all_edges = list(effect_edges) + list(fetch_edges)

    # --- Matcher ---
    opportunity_nodes: list[dict] = []
    matcher_tokens = 0
    try:
        opportunity_nodes, match_edges, matcher_tokens = await _call_with_retry(
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
    controller_tokens = 0
    try:
        ctrl, controller_tokens = await _call_with_retry(
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

    tokens_used = {
        "thinker": thinker_tokens,
        "matcher": matcher_tokens,
        "controller": controller_tokens,
    }

    return LayerResult(
        effect_nodes=effect_nodes,
        fetch_nodes=fetch_nodes,
        opportunity_nodes=opportunity_nodes,
        all_edges=all_edges,
        controller_decision=ctrl,
        tokens_used=tokens_used,
    )


async def run_layer_streaming(
    session_id: str,
    registry: SessionRegistry,
    chain_summary: str,
    parent_nodes: list[dict],
    news_pool: list[dict],
    value_pool: list[dict],
    layer: int,
    max_depth: int,
    confidence_threshold: float = 35,
) -> LayerResult:
    """Run one layer with a streaming thinker (LiteLLM) + batch matcher/controller.

    Pushes SSE events to the session queue as nodes are generated:
    - node_start, node_text, node_complete  (from thinker stream)
    - opportunity                            (from matcher batch)
    - edges                                  (after thinker + matcher)
    - layer_complete                         (after controller)
    - error                                  (on failure)
    """
    entry = registry.get(session_id)
    if entry is None:
        log.warning("run_layer_streaming: session %s not registered", session_id)
        return _empty_layer_result("Session not registered")

    queue = entry.queue

    def _push(event: str, data) -> None:
        try:
            queue.put_nowait(SSEEvent(event=event, data=data, id=uuid4().hex[:8]))
        except asyncio.QueueFull:
            log.warning("Session %s queue full, dropping event %s", session_id, event)

    try:
        # --- Thinker (streaming via LiteLLM) ---
        if not parent_nodes:
            _push("layer_complete", {"layer": layer, "reason": "no parent nodes"})
            return _empty_layer_result("No parent nodes")

        system_prompt = build_system_prompt_with_skills(allowed_skills=THINKER_SKILLS)
        user_prompt = build_thinker_prompt(
            parent_nodes=parent_nodes,
            chain_summary=chain_summary,
            news_pool=news_pool,
            layer=layer,
        )

        if litellm_acompletion is None:
            raise RuntimeError(
                "litellm is not installed — streaming thinker requires litellm"
            )

        litellm_params = get_litellm_params()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        parser = IncrementalEffectsParser()
        full_text = ""
        index_to_id: dict[int, str] = {}
        parent_ids = [n["id"] for n in parent_nodes]

        response = await litellm_acompletion(
            messages=messages, stream=True, **litellm_params
        )

        async for chunk in response:
            delta = chunk.choices[0].delta
            token = getattr(delta, "content", None) or ""
            if not token:
                continue
            full_text += token
            events = parser.feed(token)
            for ev in events:
                idx = ev["data"].get("index")
                if ev["type"] == "node_start":
                    node_id = uuid4().hex[:12]
                    index_to_id[idx] = node_id
                    _push(
                        "node_start",
                        {
                            "id": node_id,
                            "layer": layer,
                            "type": "effect",
                            "parent_ids": parent_ids,
                        },
                    )
                elif ev["type"] == "node_text":
                    node_id = index_to_id.get(idx, f"unknown-{idx}")
                    _push(
                        "node_text",
                        {
                            "id": node_id,
                            "field": ev["data"]["field"],
                            "delta": ev["data"]["delta"],
                        },
                    )
                elif ev["type"] == "node_complete":
                    node_id = index_to_id.get(idx, f"unknown-{idx}")
                    _push(
                        "node_complete",
                        {
                            "id": node_id,
                            "confidence": ev["data"].get("confidence", 0),
                            "metadata": {
                                k: v
                                for k, v in ev["data"].items()
                                if k
                                not in (
                                    "index",
                                    "content",
                                    "reasoning",
                                    "confidence",
                                )
                            },
                        },
                    )

        # Parse full response for node/edge construction
        parsed = parse_json_response(full_text)
        if not parsed or not isinstance(parsed, dict):
            log.warning("Thinker stream parse failed at layer %d", layer)
            _push("layer_complete", {"layer": layer, "reason": "parse failed"})
            return _empty_layer_result("Thinker stream parse failed")

        effects_raw = parsed.get("effects", [])
        effect_nodes, fetch_nodes, effect_edges, fetch_edges = _build_thinker_output(
            effects_raw, parent_nodes, news_pool, layer
        )

        if not effect_nodes:
            log.info("Thinker stream produced no effects at layer %d", layer)
            _push("layer_complete", {"layer": layer, "reason": "no effects"})
            return _empty_layer_result("Thinker produced no effects")

        all_edges = list(effect_edges) + list(fetch_edges)

        # Push edges from thinker
        _push("edges", {"edges": all_edges, "source": "thinker"})

        # --- Matcher (batch) ---
        opportunity_nodes: list[dict] = []
        matcher_tokens = 0
        try:
            opportunity_nodes, match_edges, matcher_tokens = await _call_with_retry(
                run_matcher,
                effects=effect_nodes,
                value_pool=value_pool,
            )
            all_edges.extend(match_edges)
            for opp in opportunity_nodes:
                _push("opportunity", opp)
            if match_edges:
                _push("edges", {"edges": match_edges, "source": "matcher"})
        except Exception as e:
            log.warning(
                "Matcher failed at layer %d (streaming), continuing: %s", layer, e
            )

        # --- Controller (batch) ---
        controller_tokens = 0
        try:
            ctrl, controller_tokens = await _call_with_retry(
                run_controller,
                chain_summary=chain_summary,
                effects=effect_nodes,
                matches=opportunity_nodes,
                layer=layer,
                max_depth=max_depth,
                confidence_threshold=confidence_threshold,
            )
        except Exception as e:
            log.warning(
                "Controller failed at layer %d (streaming), using default: %s", layer, e
            )
            should_continue = layer < DEFAULT_STOP_LAYER
            ctrl = {
                "continue": should_continue,
                "reasoning": f"Controller failed, default: {'continue' if should_continue else 'stop'}",
                "summary": chain_summary,
            }

        _push(
            "layer_complete",
            {
                "layer": layer,
                "effect_count": len(effect_nodes),
                "opportunity_count": len(opportunity_nodes),
                "controller": ctrl,
            },
        )

        tokens_used = {
            "thinker": 0,  # streaming path doesn't track tokens yet
            "matcher": matcher_tokens,
            "controller": controller_tokens,
        }

        return LayerResult(
            effect_nodes=effect_nodes,
            fetch_nodes=fetch_nodes,
            opportunity_nodes=opportunity_nodes,
            all_edges=all_edges,
            controller_decision=ctrl,
            tokens_used=tokens_used,
        )

    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.error("run_layer_streaming failed at layer %d: %s", layer, e)
        _push("error", {"layer": layer, "error": str(e)})
        return _empty_layer_result(f"Streaming layer failed: {e}")


async def run_pipeline(
    session_id: str,
    seeds: list[dict],
    news_pool: list[dict],
    value_pool: list[dict],
    max_depth: int,
    on_layer_complete: Callable,
) -> None:
    """Run the full pipeline loop: iterate layers until controller stops or max_depth."""
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
            session_id=session_id,
        )

        await on_layer_complete(layer, result)

        # Collect all new nodes for persistence + accumulation
        all_new_nodes = (
            result.effect_nodes + result.fetch_nodes + result.opportunity_nodes
        )

        # Fire-and-forget graph write (graceful degradation)
        if all_new_nodes:
            from src.graph.writer import try_ingest_thinking_layer

            try_ingest_thinking_layer(session_id, layer, all_new_nodes)

        # Accumulate this layer's nodes for future parent collection
        all_layer_nodes.append(all_new_nodes)

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
