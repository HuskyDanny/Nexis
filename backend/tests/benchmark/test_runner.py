"""Tests for benchmark runner utility functions.

Tests only wrap_skill_tool and trace I/O — run_scenario_live requires
the full pipeline and is not tested here.
"""

import json
import pytest
from pathlib import Path

from tests.benchmark.runner import wrap_skill_tool, save_trace, load_trace
from tests.benchmark.models import (
    AgentTrace,
    BenchmarkTrace,
    ControllerOutput,
    LayerTrace,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_trace(
    scenario_id: str = "sc_test", run_id: str = "run_test"
) -> BenchmarkTrace:
    ctrl = ControllerOutput(continue_=False, reasoning="done", summary="complete")
    layer = LayerTrace(
        layer=1,
        agents=[],
        nodes_produced=[],
        edges_produced=[],
        chain_summary="",
        controller_output=ctrl,
    )
    return BenchmarkTrace(
        scenario_id=scenario_id,
        run_id=run_id,
        timestamp="2026-03-23T10:00:00Z",
        model="minimax-m2.5",
        total_layers=1,
        layers=[layer],
        news_pool=[],
        value_pool=[],
        total_tokens=0,
        total_latency_ms=0,
    )


# ---------------------------------------------------------------------------
# TestWrapSkillTool
# ---------------------------------------------------------------------------


class TestWrapSkillTool:
    def test_records_skill_name(self):
        invocations: list[str] = []

        def original(skill_name):
            return f"content for {skill_name}"

        wrapped = wrap_skill_tool(original, invocations)
        result = wrapped("geopolitical_risk")

        assert invocations == ["geopolitical_risk"]
        assert result == "content for geopolitical_risk"

    def test_records_multiple_invocations(self):
        invocations: list[str] = []

        def original(skill_name):  # noqa: ARG001
            return "ok"

        wrapped = wrap_skill_tool(original, invocations)
        wrapped("geopolitical_risk")
        wrapped("macro_economics")
        wrapped("geopolitical_risk")

        assert invocations == [
            "geopolitical_risk",
            "macro_economics",
            "geopolitical_risk",
        ]

    def test_propagates_exception(self):
        invocations: list[str] = []

        def failing(skill_name):
            raise ValueError("boom")

        wrapped = wrap_skill_tool(failing, invocations)
        with pytest.raises(ValueError, match="boom"):
            wrapped("bad_skill")

        assert invocations == ["bad_skill"]

    def test_shared_invocations_list(self):
        invocations: list[str] = []

        def fn1(skill_name):  # noqa: ARG001
            return "a"

        def fn2(skill_name):  # noqa: ARG001
            return "b"

        w1 = wrap_skill_tool(fn1, invocations)
        w2 = wrap_skill_tool(fn2, invocations)
        w1("skill_a")
        w2("skill_b")

        assert invocations == ["skill_a", "skill_b"]


# ---------------------------------------------------------------------------
# TestTraceIO
# ---------------------------------------------------------------------------


class TestTraceIO:
    def test_save_and_load_roundtrip(self, tmp_path: Path):
        trace = _make_minimal_trace()
        dest = str(tmp_path / "traces" / "run_test.json")

        save_trace(trace, dest)
        loaded = load_trace(dest)

        assert loaded.scenario_id == trace.scenario_id
        assert loaded.run_id == trace.run_id
        assert loaded.model == trace.model
        assert loaded.trace_version == trace.trace_version
        assert loaded.total_layers == trace.total_layers
        assert len(loaded.layers) == 1

    def test_save_creates_parent_directories(self, tmp_path: Path):
        trace = _make_minimal_trace()
        dest = str(tmp_path / "deep" / "nested" / "dir" / "trace.json")
        save_trace(trace, dest)
        assert Path(dest).exists()

    def test_saved_file_is_valid_json(self, tmp_path: Path):
        trace = _make_minimal_trace()
        dest = str(tmp_path / "trace.json")
        save_trace(trace, dest)

        with open(dest) as f:
            data = json.load(f)
        assert data["scenario_id"] == trace.scenario_id

    def test_load_nonexistent_raises_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_trace(str(tmp_path / "does_not_exist.json"))

    def test_roundtrip_preserves_layers_and_agents(self, tmp_path: Path):
        ctrl = ControllerOutput(continue_=True, reasoning="r", summary="s")
        agent = AgentTrace(
            agent="thinker",
            input_summary="some input",
            output_raw="some output",
            skills_loaded=["macro_analysis"],
            tokens_used=50,
            latency_ms=100,
        )
        layer = LayerTrace(
            layer=1,
            agents=[agent],
            nodes_produced=[{"id": "n1", "type": "effect"}],
            edges_produced=[{"source": "n0", "target": "n1"}],
            chain_summary="chain",
            controller_output=ctrl,
        )
        trace = BenchmarkTrace(
            scenario_id="sc_rich",
            run_id="run_rich",
            timestamp="2026-03-23T12:00:00Z",
            model="minimax-m2.5",
            total_layers=1,
            layers=[layer],
            news_pool=[{"id": "news1", "title": "Test"}],
            value_pool=[{"ticker": "AAPL"}],
            total_tokens=50,
            total_latency_ms=100,
        )
        dest = str(tmp_path / "rich_trace.json")
        save_trace(trace, dest)
        loaded = load_trace(dest)

        assert loaded.layers[0].agents[0].agent == "thinker"
        assert loaded.layers[0].agents[0].skills_loaded == ["macro_analysis"]
        assert loaded.layers[0].nodes_produced[0]["id"] == "n1"
        assert loaded.news_pool[0]["id"] == "news1"
