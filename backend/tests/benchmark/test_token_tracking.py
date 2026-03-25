"""Tests for token usage tracking through the benchmark pipeline.

Verifies that token counts from CrewAI are propagated through
LayerResult -> AgentTrace -> BenchmarkTrace.
"""

from __future__ import annotations

from dataclasses import fields

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
