### Task 9: Pytest Conftest & Test Entry Point

**Files:**
- Create: `backend/tests/benchmark/conftest.py`
- Create: `backend/tests/benchmark/test_benchmark.py`
- Create: `backend/tests/benchmark/traces/.gitkeep`
- Modify: `backend/.gitignore` — ignore trace directory

**Note:** The benchmark marker was already added to `pyproject.toml` in Task 1.

**MongoDB mock note:** The root `tests/conftest.py` has `autouse=True` on `mock_mongodb`. This applies to benchmark tests. In replay mode this is harmless (no DB calls). In live mode, the runner calls `run_layer()` at the service layer — if any path touches MongoDB, the mock prevents real connections. This is acceptable since the runner doesn't need MongoDB.

- [ ] **Step 1: Write smoke test for benchmark entry point**

```python
# backend/tests/benchmark/test_benchmark.py
import pytest
from tests.benchmark.scenarios.iran_escalation import SCENARIO


@pytest.mark.benchmark
class TestBenchmark:
    def test_replay_requires_trace(self, benchmark_mode, trace_path):
        if benchmark_mode != "replay" or trace_path is None:
            pytest.skip("Replay test requires --mode=replay --trace=<path>")
        from tests.benchmark.runner import load_trace
        trace = load_trace(trace_path)
        assert trace.scenario_id == SCENARIO["id"]
```

- [ ] **Step 2: Implement conftest with CLI options**

Create `backend/tests/benchmark/conftest.py` with:
- `pytest_addoption(parser)`: --mode (replay|live), --judge (model name), --runs (int), --trace (path)
- Fixtures: `benchmark_mode`, `judge_model_name`, `judge_model` (calls create_judge_model), `num_runs`, `trace_path`

- [ ] **Step 3: Create traces directory and gitignore**

```bash
mkdir -p backend/tests/benchmark/traces/iran-escalation
touch backend/tests/benchmark/traces/.gitkeep
```

Add to `backend/.gitignore` — use recursive pattern to catch subdirectory traces:
```
# Benchmark traces (can be large, regenerated on demand)
tests/benchmark/traces/**/*.json
```

- [ ] **Step 4: Verify test isolation**

Run: `cd backend && python -m pytest tests/benchmark/ -v -m benchmark`
Expected: Smoke test SKIPPED (no trace)

Run: `cd backend && python -m pytest tests/ -v -m "not benchmark" --co | head -20`
Expected: No benchmark tests collected

- [ ] **Step 5: Commit**

```bash
git add backend/tests/benchmark/conftest.py backend/tests/benchmark/test_benchmark.py
git add backend/tests/benchmark/traces/.gitkeep backend/.gitignore
git commit -m "feat(benchmark): add pytest conftest, entry point, and trace directory"
```
