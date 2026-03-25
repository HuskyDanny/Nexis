"""Benchmark runner — wraps the pipeline with instrumentation to produce traces."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from tests.benchmark.models import (
    AgentTrace,
    BenchmarkTrace,
    ControllerOutput,
    LayerTrace,
)


def wrap_skill_tool(original_fn, invocations: list[str]):
    """Wrap the load_skill tool to record which skills are loaded."""

    def wrapper(skill_name: str) -> str:
        invocations.append(skill_name)
        return original_fn(skill_name)

    return wrapper


def save_trace(trace: BenchmarkTrace, path: str) -> None:
    """Save a trace to a JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(trace.model_dump_json(indent=2))


def load_trace(path: str) -> BenchmarkTrace:
    """Load a trace from a JSON file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Trace not found: {path}")
    return BenchmarkTrace.model_validate_json(p.read_text())


async def run_scenario_live(
    scenario: dict,
    model: str = "minimax-m2.5",
) -> BenchmarkTrace:
    """Execute a scenario through the real pipeline and capture a trace."""
    from src.services.thinking_service import run_layer

    run_id = f"run-{uuid4().hex[:8]}"
    timestamp = datetime.now(timezone.utc).isoformat()
    layers: list[LayerTrace] = []
    chain_summary = ""
    total_tokens = 0
    total_latency_ms = 0

    # Build seed nodes from news pool (layer 0)
    seeds = []
    for news in scenario["news_pool"]:
        sectors = news.get("sectors", ["unknown"])
        sector = sectors[0] if isinstance(sectors, list) and sectors else "unknown"
        seeds.append(
            {
                "id": news["id"],
                "layer": 0,
                "type": "news",
                "content": news["title"],
                "reasoning": news.get("summary", ""),
                "confidence": 100,
                "sources": [news.get("url", "")],
                "parents": [],
                "selected": True,
                "metadata": {"sector": sector},
            }
        )

    parent_nodes = seeds
    max_depth = scenario["expected_depth"]

    for layer_num in range(1, max_depth + 1):
        start_time = time.perf_counter()

        result = await run_layer(
            chain_summary=chain_summary,
            parent_nodes=parent_nodes,
            news_pool=scenario["news_pool"],
            value_pool=scenario["value_pool"],
            layer=layer_num,
            max_depth=max_depth,
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract controller output
        cd = result.controller_decision
        controller_output = ControllerOutput(
            continue_=cd.get("continue", False),
            reasoning=cd.get("reasoning", ""),
            summary=cd.get("summary", ""),
        )

        # Build all nodes for this layer
        all_nodes = result.effect_nodes + result.fetch_nodes + result.opportunity_nodes

        # Build agent traces — skills are pre-loaded into agent prompts, so we
        # record the known skill sets per agent role.
        from src.agents.thinking_helpers import THINKER_SKILLS, MATCHER_SKILLS

        thinker_skills = [s for s in THINKER_SKILLS]
        matcher_skills = [s for s in MATCHER_SKILLS]

        agent_traces = [
            AgentTrace(
                agent="thinker",
                input_summary=f"Layer {layer_num}: {len(parent_nodes)} parents, {len(scenario['news_pool'])} news",
                output_raw=json.dumps(result.effect_nodes[:3], default=str),
                skills_loaded=thinker_skills,
                tokens_used=result.tokens_used.get("thinker", 0),
                latency_ms=elapsed_ms,
            ),
            AgentTrace(
                agent="matcher",
                input_summary=f"Layer {layer_num}: {len(result.effect_nodes)} effects",
                output_raw=json.dumps(result.opportunity_nodes[:3], default=str),
                skills_loaded=matcher_skills,
                tokens_used=result.tokens_used.get("matcher", 0),
                latency_ms=0,
            ),
            AgentTrace(
                agent="controller",
                input_summary=f"Layer {layer_num}: {len(result.effect_nodes)} effects, {len(result.opportunity_nodes)} matches",
                output_raw=json.dumps(cd, default=str),
                skills_loaded=[],
                tokens_used=result.tokens_used.get("controller", 0),
                latency_ms=0,
            ),
        ]

        total_tokens += sum(result.tokens_used.values())

        layer_trace = LayerTrace(
            layer=layer_num,
            agents=agent_traces,
            nodes_produced=all_nodes,
            edges_produced=result.all_edges,
            chain_summary=controller_output.summary,
            controller_output=controller_output,
        )
        layers.append(layer_trace)

        total_latency_ms += elapsed_ms

        # Update for next layer
        chain_summary = controller_output.summary
        parent_nodes = [
            n
            for n in all_nodes
            if n.get("type") == "effect" and n.get("selected", True)
        ]

        if not controller_output.continue_:
            break

    return BenchmarkTrace(
        scenario_id=scenario["id"],
        run_id=run_id,
        trace_version=1,
        timestamp=timestamp,
        model=model,
        total_layers=len(layers),
        layers=layers,
        news_pool=scenario["news_pool"],
        value_pool=scenario["value_pool"],
        total_tokens=total_tokens,
        total_latency_ms=total_latency_ms,
    )
