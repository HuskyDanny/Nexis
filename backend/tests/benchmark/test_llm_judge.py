"""Tests for Pass 2 LLM judge with CaSE context construction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.benchmark.models import (
    AgentTrace,
    BenchmarkTrace,
    ControllerOutput,
    LayerTrace,
)
from tests.benchmark.scoring.llm_judge import (
    _make_trace,
    build_judge_input_for_layer,
    build_judge_output_for_layer,
    create_dimension_metrics,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_custom_trace(layer_summaries: list[str]) -> BenchmarkTrace:
    """Build a BenchmarkTrace with the given per-layer chain summaries."""
    layers = []
    for i, summary in enumerate(layer_summaries):
        layer = LayerTrace(
            layer=i + 1,
            agents=[
                AgentTrace(
                    agent=f"agent_{i}",
                    input_summary="some input",
                    output_raw=f"Agent {i} output: effect at layer {i + 1}",
                )
            ],
            nodes_produced=[],
            edges_produced=[],
            chain_summary=summary,
            controller_output=ControllerOutput(
                **{
                    "continue": i < len(layer_summaries) - 1,
                    "reasoning": "test reasoning",
                    "summary": summary,
                }
            ),
        )
        layers.append(layer)

    return BenchmarkTrace(
        scenario_id="test_scenario",
        run_id="run_001",
        timestamp="2026-01-01T00:00:00",
        model="test-model",
        total_layers=len(layers),
        layers=layers,
        news_pool=[
            {"title": "Military strike is likely", "source": "Reuters"},
            {"title": "Oil prices surge on tensions", "source": "Bloomberg"},
        ],
        value_pool=[],
        total_tokens=1000,
        total_latency_ms=5000.0,
    )


# ---------------------------------------------------------------------------
# TestCaSEContextConstruction
# ---------------------------------------------------------------------------


class TestCaSEContextConstruction:
    """Verify CaSE (Causal and Sequential Evidence) context slicing."""

    def test_layer1_gets_only_news(self):
        """Layer index 0 (first layer) should see news pool but no prior summaries."""
        trace = _make_custom_trace(
            [
                "Layer 1 summary: military escalation",
                "Layer 2 summary: oil prices spike",
            ]
        )
        context = build_judge_input_for_layer(trace, layer_index=0)

        assert "Military strike is likely" in context
        assert "Layer 1 summary" not in context
        assert "Layer 2 summary" not in context

    def test_layer2_gets_layer1_summary(self):
        """Layer index 1 (second layer) should see layer 1 summary but not layer 2."""
        trace = _make_custom_trace(
            [
                "Layer 1 summary: military escalation",
                "Layer 2 summary: oil prices spike",
            ]
        )
        context = build_judge_input_for_layer(trace, layer_index=1)

        assert "Layer 1 summary: military escalation" in context
        assert "Layer 2 summary" not in context

    def test_layer1_context_contains_current_label(self):
        """Context should include a current-layer label."""
        trace = _make_custom_trace(["Layer 1 summary: military escalation"])
        context = build_judge_input_for_layer(trace, layer_index=0)

        assert "Current layer 1" in context or "layer 1" in context.lower()

    def test_output_contains_agent_responses(self):
        """build_judge_output_for_layer should include each agent's output_raw."""
        trace = _make_custom_trace(
            [
                "Layer 1 summary: military escalation",
                "Layer 2 summary: oil prices spike",
            ]
        )
        output = build_judge_output_for_layer(trace, layer_index=0)

        assert "Agent 0 output: effect at layer 1" in output

    def test_output_contains_controller_reasoning(self):
        """build_judge_output_for_layer should include controller reasoning."""
        trace = _make_custom_trace(["Layer 1 summary: military escalation"])
        output = build_judge_output_for_layer(trace, layer_index=0)

        assert "test reasoning" in output

    def test_output_filters_opportunity_nodes(self):
        """build_judge_output_for_layer should include opportunity-typed nodes."""
        layers = [
            LayerTrace(
                layer=1,
                agents=[
                    AgentTrace(
                        agent="agent_0",
                        input_summary="input",
                        output_raw="agent output",
                    )
                ],
                nodes_produced=[
                    {"id": "n1", "type": "opportunity", "label": "Buy XOM"},
                    {"id": "n2", "type": "risk", "label": "Sell TLT"},
                ],
                edges_produced=[],
                chain_summary="summary",
                controller_output=ControllerOutput(
                    **{"continue": False, "reasoning": "done", "summary": "summary"}
                ),
            )
        ]
        trace = BenchmarkTrace(
            scenario_id="s1",
            run_id="r1",
            timestamp="2026-01-01T00:00:00",
            model="m",
            total_layers=1,
            layers=layers,
            news_pool=[{"title": "News A"}],
            value_pool=[],
            total_tokens=100,
            total_latency_ms=500.0,
        )
        output = build_judge_output_for_layer(trace, layer_index=0)

        assert "Buy XOM" in output
        assert "Sell TLT" not in output  # risk node filtered out


# ---------------------------------------------------------------------------
# TestDimensionMetrics
# ---------------------------------------------------------------------------


class TestDimensionMetrics:
    """Verify the four GEval dimension metrics are created correctly."""

    def test_creates_four_dimensions(self):
        """create_dimension_metrics should return exactly 4 GEval metrics."""
        mock_model = MagicMock()
        with patch("tests.benchmark.scoring.llm_judge.GEval") as MockGEval:
            MockGEval.side_effect = lambda **kwargs: MagicMock(name=kwargs.get("name"))
            metrics = create_dimension_metrics(mock_model)

        assert len(metrics) == 4

    def test_dimension_names(self):
        """The 4 metrics must have the required names."""
        mock_model = MagicMock()
        captured_names = []

        with patch("tests.benchmark.scoring.llm_judge.GEval") as MockGEval:

            def capture(**kwargs):
                m = MagicMock()
                m.name = kwargs.get("name", "")
                captured_names.append(m.name)
                return m

            MockGEval.side_effect = capture
            create_dimension_metrics(mock_model)

        expected = {
            "Reasoning Correctness",
            "Reasoning Completeness",
            "Match Quality",
            "Depth Appropriateness",
        }
        assert set(captured_names) == expected

    def test_all_metrics_include_reason(self):
        """All metrics must be created with include_reason=True."""
        mock_model = MagicMock()
        captured_kwargs = []

        with patch("tests.benchmark.scoring.llm_judge.GEval") as MockGEval:

            def capture(**kwargs):
                captured_kwargs.append(kwargs)
                return MagicMock()

            MockGEval.side_effect = capture
            create_dimension_metrics(mock_model)

        for kw in captured_kwargs:
            assert (
                kw.get("include_reason") is True
            ), f"Metric '{kw.get('name')}' missing include_reason=True"


# ---------------------------------------------------------------------------
# TestMakeTraceHelper
# ---------------------------------------------------------------------------


class TestMakeTraceHelper:
    """Verify the built-in _make_trace() helper produces a valid 2-layer trace."""

    def test_returns_benchmark_trace(self):
        trace = _make_trace()
        assert isinstance(trace, BenchmarkTrace)

    def test_has_two_layers(self):
        trace = _make_trace()
        assert len(trace.layers) == 2

    def test_layer1_summary_contains_military(self):
        trace = _make_trace()
        assert "Military strike is likely" in trace.layers[0].chain_summary

    def test_layer2_summary_contains_oil(self):
        trace = _make_trace()
        assert "Oil prices will spike" in trace.layers[1].chain_summary

    def test_news_pool_non_empty(self):
        trace = _make_trace()
        assert len(trace.news_pool) >= 1
