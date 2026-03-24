"""Benchmark entry point — run with: pytest -m benchmark

Usage:
    pytest -m benchmark --mode=replay --trace=<path> --judge=qwen3-8b
    pytest -m benchmark --mode=live --judge=claude-sonnet-4-6 --runs=3
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.benchmark.scenarios.iran_escalation import SCENARIO


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
class TestBenchmark:
    def test_replay_requires_trace(self, benchmark_mode, trace_path):
        if benchmark_mode != "replay" or trace_path is None:
            pytest.skip("Replay test requires --mode=replay --trace=<path>")
        from tests.benchmark.runner import load_trace

        trace = load_trace(trace_path)
        assert trace.scenario_id == SCENARIO["id"]
        assert len(trace.layers) >= 1


# ---------------------------------------------------------------------------
# Integration test with mock trace
# ---------------------------------------------------------------------------


def _build_mock_trace():
    """Build a mock 3-layer trace that hits Iran escalation checkpoints."""
    from tests.benchmark.models import (
        AgentTrace,
        BenchmarkTrace,
        ControllerOutput,
        LayerTrace,
    )

    return BenchmarkTrace(
        scenario_id="iran-escalation",
        run_id="mock-001",
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
                        input_summary="3 news items",
                        output_raw="Analysis of geopolitical situation",
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
                    },
                ],
                edges_produced=[
                    {"source": "news-001", "target": "e1", "relationship": "causes"}
                ],
                chain_summary="Military strike on Iran is highly probable",
                controller_output=ControllerOutput(
                    continue_=True,
                    reasoning="More depth needed",
                    summary="Military strike probable",
                ),
            ),
            LayerTrace(
                layer=2,
                agents=[
                    AgentTrace(
                        agent="thinker",
                        input_summary="effects from layer 1",
                        output_raw="Oil market impact analysis",
                        skills_loaded=["supply_chain", "geopolitical_risk"],
                        tokens_used=2500,
                        latency_ms=1800,
                    )
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
                        "reasoning": "Oil price increase benefits oil ETF",
                        "confidence": 82,
                        "metadata": {
                            "ticker": "USO",
                            "sentiment_score": 85,
                            "sector": "Energy",
                        },
                    },
                ],
                edges_produced=[
                    {"source": "e1", "target": "e2", "relationship": "causes"}
                ],
                chain_summary="Oil prices will spike due to Iran supply disruption",
                controller_output=ControllerOutput(
                    continue_=True,
                    reasoning="Deeper effects possible",
                    summary="Oil spike identified",
                ),
            ),
            LayerTrace(
                layer=3,
                agents=[
                    AgentTrace(
                        agent="thinker",
                        input_summary="effects from layer 2",
                        output_raw="Macro economic cascade analysis",
                        skills_loaded=["macro_economics"],
                        tokens_used=2800,
                        latency_ms=2000,
                    )
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
                        "reasoning": "Gold falls as USD strengthens from tight monetary policy",
                        "confidence": 70,
                        "metadata": {
                            "ticker": "GLD",
                            "sentiment_score": 25,
                            "sector": "Precious Metals",
                        },
                    },
                ],
                edges_produced=[
                    {"source": "e2", "target": "e3", "relationship": "causes"}
                ],
                chain_summary="Oil-driven inflation constrains Fed, strengthens USD, gold declines",
                controller_output=ControllerOutput(
                    continue_=False,
                    reasoning="Chain complete",
                    summary="Full causal chain resolved",
                ),
            ),
        ],
        news_pool=[
            {
                "id": "news-001",
                "title": "US Navy deploys carrier group near Iranian coast",
            },
            {
                "id": "news-002",
                "title": "Domestic political pressure mounts amid massacre fallout",
            },
            {
                "id": "news-003",
                "title": "Analysts warn of strategic timing for military action",
            },
        ],
        value_pool=[
            {"ticker": "USO", "name": "United States Oil Fund", "sector": "Energy"},
            {"ticker": "GLD", "name": "SPDR Gold Shares", "sector": "Precious Metals"},
        ],
        total_tokens=7300,
        total_latency_ms=5300,
    )


@pytest.mark.benchmark
class TestBenchmarkIntegration:
    async def test_pass1_scoring_on_mock_trace(self):
        """Verify Pass 1 scoring works end-to-end on a mock trace."""
        from tests.benchmark.scoring.checkpoint_scanner import run_pass1

        trace = _build_mock_trace()
        pass1 = await run_pass1(SCENARIO, trace, judge_model=None)

        # Mock trace is designed to hit specific checkpoints
        assert pass1.checkpoint_hit_rate >= 0.70  # At least 5/7 required
        assert pass1.match_accuracy == 1.0  # USO long + GLD short
        assert pass1.skill_compliance == 1.0  # All expected skills loaded
        assert len(pass1.checkpoints) == 9  # Total across 3 layers

    async def test_save_and_replay_mock_trace(self, tmp_path):
        """Save mock trace and verify it loads correctly."""
        from tests.benchmark.runner import load_trace, save_trace

        trace = _build_mock_trace()
        path = str(tmp_path / "iran-escalation" / "mock_trace.json")
        save_trace(trace, path)

        loaded = load_trace(path)
        assert loaded.scenario_id == "iran-escalation"
        assert loaded.total_layers == 3
        assert len(loaded.layers) == 3
