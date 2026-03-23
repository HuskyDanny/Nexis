#!/usr/bin/env python3
"""End-to-end benchmark run — exercises the full pipeline on a mock trace.

Usage:
    cd backend
    python -m tests.benchmark.run_e2e [--judge qwen3-8b] [--judge-runs 1]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from tests.benchmark.models import (
    AgentTrace,
    BenchmarkTrace,
    ControllerOutput,
    LayerTrace,
)
from tests.benchmark.scenarios.iran_escalation import SCENARIO
from tests.benchmark.scoring.checkpoint_scanner import run_pass1
from tests.benchmark.scoring.judge_models import create_judge_model
from tests.benchmark.scoring.llm_judge import run_pass2
from tests.benchmark.scoring.report import build_report, print_report


def build_mock_trace() -> BenchmarkTrace:
    """Build a 3-layer mock trace for the Iran escalation scenario."""
    return BenchmarkTrace(
        scenario_id="iran-escalation",
        run_id="e2e-001",
        trace_version=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        model="mock",
        total_layers=3,
        layers=[
            LayerTrace(
                layer=1,
                agents=[
                    AgentTrace(
                        agent="thinker",
                        input_summary="3 news items about Iran tensions",
                        output_raw=(
                            "Given the convergence of US Navy carrier deployment near "
                            "Iranian waters and intense domestic political pressure, "
                            "a military strike on Iran is highly probable. The political "
                            "timing creates a strategic window for action."
                        ),
                        skills_loaded=["geopolitical_risk"],
                        tokens_used=2000,
                        latency_ms=1500,
                    )
                ],
                nodes_produced=[
                    {
                        "id": "e1",
                        "layer": 1,
                        "type": "effect",
                        "content": "High probability of US military strike on Iran",
                        "reasoning": (
                            "Naval carrier group deployment near Iran combined with "
                            "domestic political pressure creates a strategic window "
                            "for military action. The timing of the attack aligns "
                            "with political need for distraction."
                        ),
                        "confidence": 85,
                    }
                ],
                edges_produced=[
                    {"source": "news-001", "target": "e1", "relationship": "causes"}
                ],
                chain_summary="Military strike on Iran is highly probable",
                controller_output=ControllerOutput(
                    continue_=True,
                    reasoning="First-order effect identified. Need to explore economic cascades.",
                    summary="Military strike probable given naval positioning and domestic pressure",
                ),
            ),
            LayerTrace(
                layer=2,
                agents=[
                    AgentTrace(
                        agent="thinker",
                        input_summary="Military strike effect from layer 1",
                        output_raw=(
                            "A US military strike on Iran would directly impact global "
                            "oil markets. Iran is a major oil exporter and controls the "
                            "Strait of Hormuz, through which ~20% of global oil transits. "
                            "Oil prices would spike sharply on supply disruption fears."
                        ),
                        skills_loaded=["supply_chain", "geopolitical_risk"],
                        tokens_used=2500,
                        latency_ms=1800,
                    ),
                    AgentTrace(
                        agent="matcher",
                        input_summary="Oil price spike effect",
                        output_raw="USO (oil ETF) is a direct beneficiary of rising oil prices.",
                        skills_loaded=["company_fundamentals"],
                        tokens_used=800,
                        latency_ms=600,
                    ),
                ],
                nodes_produced=[
                    {
                        "id": "e2",
                        "layer": 2,
                        "type": "effect",
                        "content": "Oil price increase due to supply disruption from Iran conflict",
                        "reasoning": (
                            "Iran is a major oil exporter and controls the Strait "
                            "of Hormuz chokepoint. Military action would disrupt "
                            "oil supply routes, causing prices to rise sharply."
                        ),
                        "confidence": 90,
                    },
                    {
                        "id": "opp1",
                        "layer": 2,
                        "type": "opportunity",
                        "content": "USO — 82% conviction",
                        "reasoning": "Oil price increase directly benefits oil ETF. Supply disruption is a strong catalyst.",
                        "confidence": 82,
                        "metadata": {
                            "ticker": "USO",
                            "sentiment_score": 85,
                            "sector": "Energy",
                        },
                    },
                ],
                edges_produced=[
                    {"source": "e1", "target": "e2", "relationship": "causes"},
                    {"source": "e2", "target": "opp1", "relationship": "matches"},
                ],
                chain_summary="Oil prices will spike due to Hormuz supply disruption",
                controller_output=ControllerOutput(
                    continue_=True,
                    reasoning="Oil spike is second-order. Macro cascades (inflation, rates) unexplored.",
                    summary="Oil spike identified via Strait of Hormuz disruption",
                ),
            ),
            LayerTrace(
                layer=3,
                agents=[
                    AgentTrace(
                        agent="thinker",
                        input_summary="Oil spike effect from layer 2",
                        output_raw=(
                            "Rising oil prices cascade into broad inflation through "
                            "transportation and production costs. The Fed cannot cut "
                            "interest rates with inflation rising, creating tight monetary "
                            "policy. USD strengthens as rates stay high. Gold, which "
                            "competes with yield-bearing USD assets, falls relative to "
                            "the strong dollar."
                        ),
                        skills_loaded=["macro_economics"],
                        tokens_used=2800,
                        latency_ms=2000,
                    ),
                    AgentTrace(
                        agent="matcher",
                        input_summary="Gold decline effect",
                        output_raw="GLD (gold ETF) should be shorted as gold falls vs strong USD.",
                        skills_loaded=["company_fundamentals"],
                        tokens_used=700,
                        latency_ms=500,
                    ),
                ],
                nodes_produced=[
                    {
                        "id": "e3",
                        "layer": 3,
                        "type": "effect",
                        "content": "Inflation increase from oil and transportation costs",
                        "reasoning": (
                            "Rising oil prices increase transportation and production "
                            "costs across the economy, pushing inflation higher. "
                            "The Fed cannot decrease interest rates in this environment, "
                            "creating tight monetary policy. USD strengthens as rates "
                            "stay high, and gold falls relative to the strong USD."
                        ),
                        "confidence": 75,
                    },
                    {
                        "id": "opp2",
                        "layer": 3,
                        "type": "opportunity",
                        "content": "GLD — 70% conviction (short)",
                        "reasoning": "Gold falls as USD strengthens from tight monetary policy driven by oil-induced inflation.",
                        "confidence": 70,
                        "metadata": {
                            "ticker": "GLD",
                            "sentiment_score": 25,
                            "sector": "Precious Metals",
                        },
                    },
                ],
                edges_produced=[
                    {"source": "e2", "target": "e3", "relationship": "causes"},
                    {"source": "e3", "target": "opp2", "relationship": "matches"},
                ],
                chain_summary="Oil-driven inflation constrains Fed, strengthens USD, gold declines",
                controller_output=ControllerOutput(
                    continue_=False,
                    reasoning="Three-layer causal chain complete. Further depth would be speculative.",
                    summary="Full chain: strike → oil → inflation → gold decline",
                ),
            ),
        ],
        news_pool=SCENARIO["news_pool"],
        value_pool=SCENARIO["value_pool"],
        total_tokens=9600,
        total_latency_ms=7400,
    )


async def main():
    parser = argparse.ArgumentParser(description="E2E benchmark run")
    parser.add_argument("--judge", default="qwen3-8b", help="Judge model name")
    parser.add_argument(
        "--judge-runs", type=int, default=1, help="Judge consistency runs"
    )
    parser.add_argument(
        "--pass2", action="store_true", help="Run Pass 2 (LLM judge, costs tokens)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  BENCHMARK E2E RUN")
    print("=" * 60)

    # Step 1: Build mock trace
    print("\n[1/4] Building mock trace...")
    trace = build_mock_trace()
    print(
        f"  Trace: {trace.scenario_id}, {trace.total_layers} layers, {trace.total_tokens} tokens"
    )

    # Step 2: Run Pass 1 (checkpoint scanning)
    print("\n[2/4] Running Pass 1 (checkpoint scanning)...")
    pass1 = await run_pass1(SCENARIO, trace, judge_model=None)
    print(f"  Checkpoint hit rate (required): {pass1.checkpoint_hit_rate:.0%}")
    print(f"  Match accuracy: {pass1.match_accuracy:.0%}")
    print(f"  Skill compliance: {pass1.skill_compliance:.0%}")

    # Step 3: Run Pass 2 (LLM judge) — optional
    pass2 = None
    if args.pass2:
        print(
            f"\n[3/4] Running Pass 2 (LLM judge: {args.judge}, {args.judge_runs}x)..."
        )
        try:
            judge_model = create_judge_model(args.judge)
            pass2 = run_pass2(trace, judge_model, judge_runs=args.judge_runs)
            for dim in pass2.dimensions:
                print(f"  {dim.name}: {dim.score:.2f}")
                if dim.reason:
                    print(f"    → {dim.reason[:80]}")
        except Exception as e:
            print(f"  WARN: Pass 2 failed: {e}")
            print("  Continuing with Pass 1 only...")
    else:
        print("\n[3/4] Skipping Pass 2 (use --pass2 to enable LLM judge)")

    # Step 4: Build and print report
    print("\n[4/4] Building report...")
    from tests.benchmark.models import Pass2Scores

    if pass2 is None:
        pass2 = Pass2Scores()

    report = build_report(
        scenario=SCENARIO,
        trace=trace,
        pass1=pass1,
        pass2=pass2,
        mode="replay",
        judge_model_name=args.judge if args.pass2 else "none",
        judge_runs=args.judge_runs,
    )

    print_report(report)

    # Save trace for future replay
    from tests.benchmark.runner import save_trace

    trace_path = "tests/benchmark/traces/iran-escalation/e2e_trace.json"
    save_trace(trace, trace_path)
    print(f"\n  Trace saved to: {trace_path}")

    return report


if __name__ == "__main__":
    report = asyncio.run(main())
    # Exit 0 always — the score is informational, not a gate
    sys.exit(0)
