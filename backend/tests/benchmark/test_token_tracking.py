"""Tests for token usage tracking through the benchmark pipeline.

Verifies that token counts from CrewAI are propagated through
LayerResult -> AgentTrace -> BenchmarkTrace.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from src.services.thinking_service import LayerResult
from tests.benchmark.models import AgentTrace, BenchmarkTrace


class TestLayerResultTokenField:
    """LayerResult must carry token counts from agent executions."""

    def test_layer_result_has_tokens_used_field(self):
        """LayerResult dataclass must have a tokens_used dict field."""
        field_names = {f.name for f in fields(LayerResult)}
        assert "tokens_used" in field_names

    def test_layer_result_tokens_default_empty(self):
        """tokens_used defaults to empty dict when not provided."""
        result = LayerResult()
        assert result.tokens_used == {}

    def test_layer_result_tokens_stores_per_agent(self):
        """tokens_used stores per-agent token counts."""
        result = LayerResult(
            tokens_used={"thinker": 150, "matcher": 80, "controller": 30}
        )
        assert result.tokens_used["thinker"] == 150
        assert result.tokens_used["matcher"] == 80
        assert result.tokens_used["controller"] == 30


class TestAgentTraceTokens:
    """AgentTrace.tokens_used must accept non-zero values from pipeline."""

    def test_agent_trace_preserves_token_count(self):
        """AgentTrace stores the token count passed to it."""
        trace = AgentTrace(
            agent="thinker",
            input_summary="test",
            output_raw="{}",
            tokens_used=250,
            latency_ms=100,
        )
        assert trace.tokens_used == 250

    def test_benchmark_trace_total_tokens_nonzero(self):
        """BenchmarkTrace.total_tokens should reflect sum of agent tokens."""
        # This is a data integrity test — if total_tokens is hardcoded to 0
        # in the runner, this test documents the expectation that it should
        # reflect actual usage.
        from tests.benchmark.models import ControllerOutput, LayerTrace

        agent = AgentTrace(
            agent="thinker",
            input_summary="test",
            output_raw="{}",
            tokens_used=500,
            latency_ms=100,
        )
        ctrl = ControllerOutput(continue_=False, reasoning="done", summary="s")
        layer = LayerTrace(
            layer=1,
            agents=[agent],
            nodes_produced=[],
            edges_produced=[],
            chain_summary="",
            controller_output=ctrl,
        )
        trace = BenchmarkTrace(
            scenario_id="test",
            run_id="run-test",
            timestamp="2026-03-25T00:00:00Z",
            model="test",
            total_layers=1,
            layers=[layer],
            news_pool=[],
            value_pool=[],
            total_tokens=500,
            total_latency_ms=100,
        )
        assert trace.total_tokens == 500
        assert trace.layers[0].agents[0].tokens_used == 500


class TestTokenAggregationThroughRunner:
    """Verify token counts propagate through run_scenario_live."""

    @staticmethod
    def _make_layer_result(thinker_tok: int, matcher_tok: int, ctrl_tok: int):
        """Build a LayerResult with specified token counts."""
        return LayerResult(
            effect_nodes=[
                {
                    "id": "eff-1",
                    "layer": 1,
                    "type": "effect",
                    "content": "test effect",
                    "reasoning": "",
                    "confidence": 80,
                    "sources": [],
                    "parents": ["seed-1"],
                    "selected": True,
                    "metadata": {},
                }
            ],
            fetch_nodes=[],
            opportunity_nodes=[],
            all_edges=[],
            controller_decision={
                "continue": False,
                "reasoning": "done",
                "summary": "summary",
            },
            tokens_used={
                "thinker": thinker_tok,
                "matcher": matcher_tok,
                "controller": ctrl_tok,
            },
        )

    @pytest.mark.asyncio
    async def test_single_layer_token_aggregation(self):
        """Tokens from a single layer flow into BenchmarkTrace.total_tokens."""
        from unittest.mock import AsyncMock, patch

        scenario = {
            "id": "test-agg",
            "news_pool": [
                {
                    "id": "n1",
                    "title": "Test News",
                    "summary": "s",
                    "sectors": ["tech"],
                }
            ],
            "value_pool": [{"ticker": "AAPL", "sector": "tech"}],
            "expected_depth": 1,
        }

        fake_result = self._make_layer_result(200, 100, 50)

        with patch(
            "src.services.thinking_service.run_layer", new_callable=AsyncMock
        ) as mock_rl:
            mock_rl.return_value = fake_result
            from tests.benchmark.runner import run_scenario_live

            trace = await run_scenario_live(scenario)

        assert trace.total_tokens == 350
        assert len(trace.layers) == 1
        agents = trace.layers[0].agents
        assert agents[0].tokens_used == 200  # thinker
        assert agents[1].tokens_used == 100  # matcher
        assert agents[2].tokens_used == 50  # controller

    @pytest.mark.asyncio
    async def test_multi_layer_token_aggregation(self):
        """Tokens accumulate across multiple layers."""
        from unittest.mock import AsyncMock, patch

        scenario = {
            "id": "test-multi",
            "news_pool": [
                {
                    "id": "n1",
                    "title": "Test",
                    "summary": "s",
                    "sectors": ["tech"],
                }
            ],
            "value_pool": [{"ticker": "AAPL", "sector": "tech"}],
            "expected_depth": 2,
        }

        layer1 = self._make_layer_result(200, 100, 50)
        # Layer 1 continues so layer 2 runs
        layer1.controller_decision["continue"] = True
        layer1.controller_decision["summary"] = "layer 1 done"

        layer2 = self._make_layer_result(150, 80, 30)

        with patch(
            "src.services.thinking_service.run_layer", new_callable=AsyncMock
        ) as mock_rl:
            mock_rl.side_effect = [layer1, layer2]
            from tests.benchmark.runner import run_scenario_live

            trace = await run_scenario_live(scenario)

        assert trace.total_tokens == 610  # 350 + 260
        assert len(trace.layers) == 2
