### Task 6: LLM Judge — Pass 2 with CaSE

**Files:**
- Create: `backend/tests/benchmark/scoring/llm_judge.py`
- Test: `backend/tests/benchmark/test_llm_judge.py`

**Reference:** DeepEval GEval — `GEval(name, criteria, include_reason, model, evaluation_params)`

- [ ] **Step 1: Write failing tests for LLM judge**

```python
# backend/tests/benchmark/test_llm_judge.py
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from tests.benchmark.scoring.llm_judge import (
    build_judge_input_for_layer, build_judge_output_for_layer, create_dimension_metrics,
)
from tests.benchmark.models import BenchmarkTrace, LayerTrace, AgentTrace, ControllerOutput


def _make_trace():
    return BenchmarkTrace(
        scenario_id="test", run_id="r1", trace_version=1,
        timestamp=datetime.now(timezone.utc), model="test", total_layers=2,
        layers=[
            LayerTrace(layer=1, agents=[AgentTrace(agent="thinker", input_summary="news",
                output_raw="Military strike is likely", skills_loaded=["geopolitical_risk"],
                tokens_used=1000, latency_ms=500)],
                nodes_produced=[{"id": "n1", "content": "Strike likely"}], edges_produced=[],
                chain_summary="Military action probable",
                controller_output=ControllerOutput(continue_=True, reasoning="More depth",
                    summary="Military action probable")),
            LayerTrace(layer=2, agents=[AgentTrace(agent="thinker", input_summary="effects",
                output_raw="Oil prices will spike", skills_loaded=["supply_chain"],
                tokens_used=1200, latency_ms=600)],
                nodes_produced=[{"id": "n2", "content": "Oil spike"}], edges_produced=[],
                chain_summary="Oil impact identified",
                controller_output=ControllerOutput(continue_=False, reasoning="Sufficient depth",
                    summary="Oil impact identified")),
        ],
        news_pool=[{"title": "Navy near Iran"}], value_pool=[{"ticker": "USO"}],
        total_tokens=2200, total_latency_ms=1100,
    )


class TestCaSEContextConstruction:
    def test_layer1_gets_only_news(self):
        context = build_judge_input_for_layer(_make_trace(), layer_index=0)
        assert "Navy near Iran" in context
        assert "Military action probable" not in context  # No hindsight

    def test_layer2_gets_layer1_summary(self):
        context = build_judge_input_for_layer(_make_trace(), layer_index=1)
        assert "Military action probable" in context
        assert "Oil impact identified" not in context

    def test_output_contains_agent_responses(self):
        output = build_judge_output_for_layer(_make_trace(), layer_index=0)
        assert "Military strike is likely" in output


class TestDimensionMetrics:
    def test_creates_four_dimensions(self):
        metrics = create_dimension_metrics(MagicMock())
        names = [m.name for m in metrics]
        assert len(metrics) == 4
        assert "Reasoning Correctness" in names
        assert "Reasoning Completeness" in names
        assert "Match Quality" in names
        assert "Depth Appropriateness" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/benchmark/test_llm_judge.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement LLM judge with CaSE**

Create `backend/tests/benchmark/scoring/llm_judge.py` with:
- `build_judge_input_for_layer(trace, layer_index) -> str`: CaSE context — news pool + chain summaries from layers BEFORE current. No hindsight.
- `build_judge_output_for_layer(trace, layer_index) -> str`: agent output_raw + opportunity nodes + controller reasoning
- `create_dimension_metrics(judge_model) -> list[GEval]`: 4 metrics — Reasoning Correctness, Reasoning Completeness, Match Quality, Depth Appropriateness. All with `include_reason=True`.
- `score_with_consistency(metric, test_case, runs=3) -> tuple[float, str, list[float]]`: run N times, return median score + reason + all scores
- `run_pass2(trace, judge_model, judge_runs=3) -> Pass2Scores`: score each dimension across all layers (average), plus bonus insights (full-trace). Use worst-scoring layer's reason as most actionable feedback.
- `_summarize_news(news_pool) -> str`: join titles for context

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/benchmark/test_llm_judge.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/benchmark/scoring/llm_judge.py backend/tests/benchmark/test_llm_judge.py
git commit -m "feat(benchmark): add Pass 2 LLM judge with CaSE and consistency scoring"
```
