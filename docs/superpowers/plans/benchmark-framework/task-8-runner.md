### Task 8: Benchmark Runner (Instrumented Pipeline Executor)

**Files:**
- Create: `backend/tests/benchmark/runner.py`
- Test: `backend/tests/benchmark/test_runner.py`

**Reference:** `backend/src/services/thinking_service.py:run_layer()`, `backend/src/agents/thinking_crew.py`

- [ ] **Step 1: Write failing tests for the runner**

```python
# backend/tests/benchmark/test_runner.py
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock
from tests.benchmark.runner import wrap_skill_tool, load_trace, save_trace
from tests.benchmark.models import BenchmarkTrace


class TestWrapSkillTool:
    def test_records_skill_invocations(self):
        invocations = []
        original = MagicMock(return_value="content")
        wrapped = wrap_skill_tool(original, invocations)
        wrapped("geopolitical_risk")
        wrapped("macro_economics")
        assert invocations == ["geopolitical_risk", "macro_economics"]


class TestTraceIO:
    def test_save_and_load_roundtrip(self, tmp_path):
        trace = BenchmarkTrace(
            scenario_id="test", run_id="r1", trace_version=1,
            timestamp=datetime.now(timezone.utc), model="test",
            total_layers=0, layers=[], news_pool=[], value_pool=[],
            total_tokens=0, total_latency_ms=0)
        path = tmp_path / "trace.json"
        save_trace(trace, str(path))
        loaded = load_trace(str(path))
        assert loaded.scenario_id == "test"

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_trace(str(tmp_path / "nope.json"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/benchmark/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement benchmark runner**

Create `backend/tests/benchmark/runner.py` with:
- `wrap_skill_tool(original_fn, invocations: list) -> callable`: wrapper that records skill name then calls original
- `run_scenario_live(scenario, model="minimax-m2.5") -> BenchmarkTrace`: async function that:
  1. Builds seed nodes from news_pool (layer 0)
  2. Loops layers 1..max_depth, calling `run_layer()` from thinking_service
  3. Wraps each call with `time.perf_counter()` for latency
  4. Extracts controller output as ControllerOutput model
  5. Collects all nodes/edges into LayerTrace
  6. Stops when controller says stop or max_depth reached
  7. Returns complete BenchmarkTrace

  Note: Token counting and skill tracking have TODO markers — they require deeper CrewAI instrumentation that will be wired in a follow-up.
- `save_trace(trace, path) -> None`: write JSON, create parent dirs
- `load_trace(path) -> BenchmarkTrace`: read JSON, raise FileNotFoundError if missing

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/benchmark/test_runner.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/benchmark/runner.py backend/tests/benchmark/test_runner.py
git commit -m "feat(benchmark): add instrumented pipeline runner with trace capture"
```
