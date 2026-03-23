import json
import pytest
from tests.benchmark.models import (
    AgentTrace,
    ControllerOutput,
    LayerTrace,
    BenchmarkTrace,
    CheckpointResult,
    MatchResult,
    SkillResult,
    DimensionScore,
    Pass1Report,
    Pass2Scores,
    BenchmarkReport,
    AggregateReport,
)


# --- AgentTrace ---


def test_agent_trace_creation():
    trace = AgentTrace(
        agent="news_analyst",
        input_summary="Fed holds rates",
        output_raw="Effect: bond yields stabilize",
        skills_loaded=["macro_analysis"],
        tokens_used=150,
        latency_ms=320.5,
    )
    assert trace.agent == "news_analyst"
    assert trace.input_summary == "Fed holds rates"
    assert trace.output_raw == "Effect: bond yields stabilize"
    assert trace.skills_loaded == ["macro_analysis"]
    assert trace.tokens_used == 150
    assert trace.latency_ms == 320.5


def test_agent_trace_defaults():
    trace = AgentTrace(
        agent="effect_agent",
        input_summary="some input",
        output_raw="some output",
    )
    assert trace.skills_loaded == []
    assert trace.tokens_used == 0
    assert trace.latency_ms == 0.0


# --- ControllerOutput ---


def test_controller_output_creation():
    ctrl = ControllerOutput(
        **{
            "continue": True,
            "reasoning": "More layers needed",
            "summary": "Proceed to layer 2",
        }
    )
    assert ctrl.continue_ is True
    assert ctrl.reasoning == "More layers needed"
    assert ctrl.summary == "Proceed to layer 2"


def test_controller_output_alias_serialization():
    ctrl = ControllerOutput(
        **{"continue": False, "reasoning": "Done", "summary": "Stop here"}
    )
    data = ctrl.model_dump(by_alias=True)
    assert "continue" in data
    assert data["continue"] is False


def test_controller_output_populate_by_name():
    # Should also accept continue_ as field name directly
    ctrl = ControllerOutput(continue_=True, reasoning="r", summary="s")
    assert ctrl.continue_ is True


# --- LayerTrace ---


def test_layer_trace_creation():
    ctrl = ControllerOutput(continue_=True, reasoning="r", summary="s")
    agent_trace = AgentTrace(
        agent="news_analyst",
        input_summary="inp",
        output_raw="out",
    )
    layer = LayerTrace(
        layer=1,
        agents=[agent_trace],
        nodes_produced=[{"id": "n1", "content": "effect"}],
        edges_produced=[{"source": "n0", "target": "n1"}],
        chain_summary="Layer 1 analysis",
        controller_output=ctrl,
    )
    assert layer.layer == 1
    assert len(layer.agents) == 1
    assert len(layer.nodes_produced) == 1
    assert len(layer.edges_produced) == 1
    assert layer.chain_summary == "Layer 1 analysis"
    assert layer.controller_output.continue_ is True


def test_layer_trace_defaults():
    ctrl = ControllerOutput(continue_=False, reasoning="r", summary="s")
    layer = LayerTrace(
        layer=0,
        agents=[],
        nodes_produced=[],
        edges_produced=[],
        chain_summary="",
        controller_output=ctrl,
    )
    assert layer.agents == []
    assert layer.nodes_produced == []
    assert layer.edges_produced == []


# --- BenchmarkTrace ---


def test_benchmark_trace_creation():
    ctrl = ControllerOutput(continue_=False, reasoning="done", summary="complete")
    layer = LayerTrace(
        layer=1,
        agents=[],
        nodes_produced=[],
        edges_produced=[],
        chain_summary="",
        controller_output=ctrl,
    )
    trace = BenchmarkTrace(
        scenario_id="sc_001",
        run_id="run_abc",
        timestamp="2026-03-23T10:00:00Z",
        model="minimax-m2.5",
        total_layers=1,
        layers=[layer],
        news_pool=[{"id": "n1", "title": "Fed holds"}],
        value_pool=[{"ticker": "AAPL"}],
        total_tokens=500,
        total_latency_ms=1200.0,
    )
    assert trace.scenario_id == "sc_001"
    assert trace.run_id == "run_abc"
    assert trace.trace_version == 1
    assert trace.model == "minimax-m2.5"
    assert trace.total_layers == 1
    assert len(trace.layers) == 1
    assert len(trace.news_pool) == 1
    assert len(trace.value_pool) == 1
    assert trace.total_tokens == 500
    assert trace.total_latency_ms == 1200.0


def test_benchmark_trace_default_version():
    trace = BenchmarkTrace(
        scenario_id="sc_002",
        run_id="run_xyz",
        timestamp="2026-03-23T10:00:00Z",
        model="qwen3-8b",
        total_layers=0,
        layers=[],
        news_pool=[],
        value_pool=[],
        total_tokens=0,
        total_latency_ms=0.0,
    )
    assert trace.trace_version == 1


def test_benchmark_trace_json_roundtrip():
    ctrl = ControllerOutput(continue_=True, reasoning="r", summary="s")
    agent = AgentTrace(
        agent="test_agent",
        input_summary="input",
        output_raw="output",
        skills_loaded=["skill_a"],
        tokens_used=100,
        latency_ms=50.0,
    )
    layer = LayerTrace(
        layer=1,
        agents=[agent],
        nodes_produced=[{"id": "x", "type": "effect"}],
        edges_produced=[],
        chain_summary="summary",
        controller_output=ctrl,
    )
    trace = BenchmarkTrace(
        scenario_id="sc_rt",
        run_id="run_rt",
        timestamp="2026-03-23T12:00:00Z",
        model="minimax-m2.5",
        total_layers=1,
        layers=[layer],
        news_pool=[],
        value_pool=[],
        total_tokens=100,
        total_latency_ms=50.0,
    )
    json_str = trace.model_dump_json()
    restored = BenchmarkTrace.model_validate_json(json_str)
    assert restored.scenario_id == trace.scenario_id
    assert restored.run_id == trace.run_id
    assert restored.trace_version == trace.trace_version
    assert len(restored.layers) == 1
    assert restored.layers[0].agents[0].agent == "test_agent"
    assert restored.layers[0].agents[0].skills_loaded == ["skill_a"]


# --- CheckpointResult ---


def test_checkpoint_result_creation():
    cp = CheckpointResult(
        layer=1,
        concept="rate hike impact",
        required=True,
        hit=True,
        method="keyword",
        matched_node_id="n_abc",
        direction_correct=True,
        evidence="Found 'rate hike' in node content",
    )
    assert cp.layer == 1
    assert cp.concept == "rate hike impact"
    assert cp.required is True
    assert cp.hit is True
    assert cp.method == "keyword"
    assert cp.matched_node_id == "n_abc"
    assert cp.direction_correct is True
    assert cp.evidence == "Found 'rate hike' in node content"


def test_checkpoint_result_llm_method():
    cp = CheckpointResult(
        layer=2,
        concept="bond yield",
        required=False,
        hit=False,
        method="llm",
        matched_node_id=None,
        direction_correct=None,
        evidence="No matching node found",
    )
    assert cp.method == "llm"
    assert cp.hit is False
    assert cp.matched_node_id is None
    assert cp.direction_correct is None


# --- MatchResult ---


def test_match_result_correct():
    m = MatchResult(
        ticker="AAPL",
        expected_direction="up",
        found=True,
        actual_direction="up",
        correct=True,
    )
    assert m.ticker == "AAPL"
    assert m.expected_direction == "up"
    assert m.found is True
    assert m.actual_direction == "up"
    assert m.correct is True


def test_match_result_not_found():
    m = MatchResult(
        ticker="NVDA",
        expected_direction="down",
        found=False,
        actual_direction=None,
        correct=False,
    )
    assert m.found is False
    assert m.actual_direction is None
    assert m.correct is False


# --- SkillResult ---


def test_skill_result_all_loaded():
    sr = SkillResult(
        layer=1,
        expected_skills=["macro_analysis", "sector_rotation"],
        actual_skills=["macro_analysis", "sector_rotation"],
        all_loaded=True,
    )
    assert sr.layer == 1
    assert sr.all_loaded is True


def test_skill_result_partial():
    sr = SkillResult(
        layer=2,
        expected_skills=["macro_analysis", "sector_rotation"],
        actual_skills=["macro_analysis"],
        all_loaded=False,
    )
    assert sr.all_loaded is False
    assert len(sr.actual_skills) == 1


# --- DimensionScore ---


def test_dimension_score_creation():
    ds = DimensionScore(
        name="causal_depth",
        score=0.85,
        reason="Strong causal chains identified",
        runs=[0.80, 0.85, 0.90],
    )
    assert ds.name == "causal_depth"
    assert ds.score == 0.85
    assert ds.reason == "Strong causal chains identified"
    assert ds.runs == [0.80, 0.85, 0.90]


def test_dimension_score_boundary_values():
    ds_zero = DimensionScore(name="dim", score=0.0, reason="r", runs=[])
    ds_one = DimensionScore(name="dim", score=1.0, reason="r", runs=[1.0])
    assert ds_zero.score == 0.0
    assert ds_one.score == 1.0


# --- Pass1Report ---


def test_pass1_report_creation():
    cp = CheckpointResult(
        layer=1,
        concept="c",
        required=True,
        hit=True,
        method="keyword",
        matched_node_id="n1",
        direction_correct=True,
        evidence="e",
    )
    m = MatchResult(
        ticker="AAPL",
        expected_direction="up",
        found=True,
        actual_direction="up",
        correct=True,
    )
    sr = SkillResult(
        layer=1, expected_skills=["s1"], actual_skills=["s1"], all_loaded=True
    )
    report = Pass1Report(
        checkpoints=[cp],
        checkpoint_hit_rate=1.0,
        checkpoint_hit_rate_all=0.9,
        matches=[m],
        match_accuracy=1.0,
        skills=[sr],
        skill_compliance=1.0,
        total_tokens=300,
        total_latency_ms=900.0,
        tokens_per_layer=150.0,
        latency_per_layer=450.0,
    )
    assert len(report.checkpoints) == 1
    assert report.checkpoint_hit_rate == 1.0
    assert report.checkpoint_hit_rate_all == 0.9
    assert len(report.matches) == 1
    assert report.match_accuracy == 1.0
    assert len(report.skills) == 1
    assert report.skill_compliance == 1.0
    assert report.total_tokens == 300
    assert report.total_latency_ms == 900.0
    assert report.tokens_per_layer == 150.0
    assert report.latency_per_layer == 450.0


# --- Pass2Scores ---


def test_pass2_scores_creation():
    ds = DimensionScore(name="causal_depth", score=0.8, reason="r", runs=[0.8])
    p2 = Pass2Scores(
        dimensions=[ds],
        bonus_insights=["Identified cross-sector compounding"],
        bonus_score=0.1,
    )
    assert len(p2.dimensions) == 1
    assert p2.dimensions[0].name == "causal_depth"
    assert len(p2.bonus_insights) == 1
    assert p2.bonus_score == 0.1


def test_pass2_scores_defaults():
    p2 = Pass2Scores(dimensions=[], bonus_insights=[], bonus_score=0.0)
    assert p2.dimensions == []
    assert p2.bonus_insights == []
    assert p2.bonus_score == 0.0


# --- BenchmarkReport ---


def test_benchmark_report_creation():
    cp = CheckpointResult(
        layer=1,
        concept="c",
        required=True,
        hit=True,
        method="keyword",
        matched_node_id="n1",
        direction_correct=True,
        evidence="e",
    )
    p1 = Pass1Report(
        checkpoints=[cp],
        checkpoint_hit_rate=1.0,
        checkpoint_hit_rate_all=1.0,
        matches=[],
        match_accuracy=0.0,
        skills=[],
        skill_compliance=1.0,
        total_tokens=200,
        total_latency_ms=500.0,
        tokens_per_layer=100.0,
        latency_per_layer=250.0,
    )
    ds = DimensionScore(name="causal_depth", score=0.75, reason="r", runs=[0.75])
    p2 = Pass2Scores(dimensions=[ds], bonus_insights=[], bonus_score=0.0)
    report = BenchmarkReport(
        scenario_id="sc_001",
        run_id="run_001",
        timestamp="2026-03-23T10:00:00Z",
        mode="deterministic",
        execution_model="minimax-m2.5",
        judge_model="claude-3-5-sonnet",
        judge_runs=3,
        pass1=p1,
        pass2=p2,
        overall_score=0.82,
        grade="B",
    )
    assert report.scenario_id == "sc_001"
    assert report.run_id == "run_001"
    assert report.mode == "deterministic"
    assert report.execution_model == "minimax-m2.5"
    assert report.judge_model == "claude-3-5-sonnet"
    assert report.judge_runs == 3
    assert report.overall_score == 0.82
    assert report.grade == "B"


# --- AggregateReport ---


def test_aggregate_report_creation():
    cp = CheckpointResult(
        layer=1,
        concept="c",
        required=True,
        hit=True,
        method="keyword",
        matched_node_id="n1",
        direction_correct=True,
        evidence="e",
    )
    p1 = Pass1Report(
        checkpoints=[cp],
        checkpoint_hit_rate=1.0,
        checkpoint_hit_rate_all=1.0,
        matches=[],
        match_accuracy=0.0,
        skills=[],
        skill_compliance=1.0,
        total_tokens=200,
        total_latency_ms=500.0,
        tokens_per_layer=100.0,
        latency_per_layer=250.0,
    )
    p2 = Pass2Scores(dimensions=[], bonus_insights=[], bonus_score=0.0)
    report = BenchmarkReport(
        scenario_id="sc_001",
        run_id="run_001",
        timestamp="2026-03-23T10:00:00Z",
        mode="deterministic",
        execution_model="minimax-m2.5",
        judge_model="claude-3-5-sonnet",
        judge_runs=3,
        pass1=p1,
        pass2=p2,
        overall_score=0.82,
        grade="B",
    )
    agg = AggregateReport(
        scenario_id="sc_001",
        num_runs=1,
        reports=[report],
        mean_overall=0.82,
        std_overall=0.0,
        min_overall=0.82,
        max_overall=0.82,
        is_stable=True,
    )
    assert agg.scenario_id == "sc_001"
    assert agg.num_runs == 1
    assert len(agg.reports) == 1
    assert agg.mean_overall == 0.82
    assert agg.std_overall == 0.0
    assert agg.min_overall == 0.82
    assert agg.max_overall == 0.82
    assert agg.is_stable is True
