### Task 2: Pydantic Trace & Report Models

**Files:**
- Create: `backend/tests/benchmark/__init__.py`
- Create: `backend/tests/benchmark/models.py`
- Test: `backend/tests/benchmark/test_models.py`

- [ ] **Step 1: Write failing test for trace models**

```python
# backend/tests/benchmark/test_models.py
import pytest
from datetime import datetime, timezone

from tests.benchmark.models import (
    AgentTrace, ControllerOutput, LayerTrace, BenchmarkTrace,
    CheckpointResult, MatchResult, SkillResult, DimensionScore,
    Pass1Report, Pass2Scores, BenchmarkReport,
)


class TestTraceModels:
    def test_agent_trace_creation(self):
        trace = AgentTrace(
            agent="thinker", input_summary="Layer 1 input with 3 news items",
            output_raw='{"effects": []}',
            skills_loaded=["geopolitical_risk", "macro_economics"],
            tokens_used=1500, latency_ms=2100,
        )
        assert trace.agent == "thinker"
        assert len(trace.skills_loaded) == 2

    def test_controller_output_creation(self):
        output = ControllerOutput(
            continue_=True, reasoning="More causal depth available",
            summary="Military strike likely, oil impact not yet explored",
        )
        assert output.continue_ is True

    def test_layer_trace_creation(self):
        layer = LayerTrace(
            layer=1,
            agents=[AgentTrace(agent="thinker", input_summary="test",
                output_raw="test", skills_loaded=[], tokens_used=100, latency_ms=500)],
            nodes_produced=[{"id": "n1", "type": "effect", "content": "oil goes up"}],
            edges_produced=[{"source": "n0", "target": "n1", "relationship": "causes"}],
            chain_summary="Oil prices expected to rise",
            controller_output=ControllerOutput(continue_=True, reasoning="More depth", summary="Oil impact"),
        )
        assert layer.layer == 1
        assert len(layer.nodes_produced) == 1

    def test_benchmark_trace_json_roundtrip(self):
        trace = BenchmarkTrace(
            scenario_id="test", run_id="r1", trace_version=1,
            timestamp=datetime.now(timezone.utc), model="test",
            total_layers=0, layers=[], news_pool=[], value_pool=[],
            total_tokens=0, total_latency_ms=0,
        )
        json_str = trace.model_dump_json()
        restored = BenchmarkTrace.model_validate_json(json_str)
        assert restored.scenario_id == trace.scenario_id


class TestReportModels:
    def test_checkpoint_result(self):
        result = CheckpointResult(
            layer=1, concept="military strike on Iran", required=True,
            hit=True, method="keyword", matched_node_id="n1", direction_correct=True,
        )
        assert result.hit is True

    def test_dimension_score(self):
        score = DimensionScore(
            name="Reasoning Correctness", score=0.85,
            reason="Causal chain is logically sound", runs=[0.80, 0.85, 0.90],
        )
        assert len(score.runs) == 3

    def test_benchmark_report(self):
        report = BenchmarkReport(
            scenario_id="test", run_id="r1", timestamp=datetime.now(timezone.utc),
            mode="replay", execution_model="test", judge_model="test", judge_runs=3,
            overall_score=0.82, grade="B",
        )
        assert report.grade == "B"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/benchmark/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement trace and report models**

Create `backend/tests/benchmark/__init__.py` (empty).

Create `backend/tests/benchmark/models.py` with these Pydantic models:
- `AgentTrace` — agent name, input_summary, output_raw, skills_loaded, tokens_used, latency_ms
- `ControllerOutput` — continue_ (bool, alias "continue"), reasoning, summary. Use `populate_by_name=True`
- `LayerTrace` — layer int, agents list, nodes_produced list[dict], edges_produced list[dict], chain_summary, controller_output
- `BenchmarkTrace` — scenario_id, run_id, trace_version (int=1), timestamp, model, total_layers, layers, news_pool, value_pool, total_tokens, total_latency_ms
- `CheckpointResult` — layer, concept, required, hit, method ("keyword"|"llm"), matched_node_id, direction_correct, evidence
- `MatchResult` — ticker, expected_direction, found, actual_direction, correct
- `SkillResult` — layer, expected_skills, actual_skills, all_loaded
- `DimensionScore` — name, score (0.0-1.0), reason, runs list[float]
- `Pass1Report` — checkpoints, checkpoint_hit_rate, checkpoint_hit_rate_all, matches, match_accuracy, skills, skill_compliance, total_tokens, total_latency_ms, tokens_per_layer, latency_per_layer
- `Pass2Scores` — dimensions list[DimensionScore], bonus_insights list[str], bonus_score
- `BenchmarkReport` — scenario_id, run_id, timestamp, mode, execution_model, judge_model, judge_runs, pass1, pass2, overall_score, grade
- `AggregateReport` — scenario_id, num_runs, reports, mean_overall, std_overall, min_overall, max_overall, is_stable

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/benchmark/test_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/benchmark/__init__.py backend/tests/benchmark/models.py backend/tests/benchmark/test_models.py
git commit -m "feat(benchmark): add Pydantic trace and report models"
```
