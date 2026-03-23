### Task 10: Full Integration Test with Mock Trace

**Files:**
- Modify: `backend/tests/benchmark/test_benchmark.py` — add integration test class
- Create: mock trace JSON via test

- [ ] **Step 1: Write integration test with mock trace**

Add `TestBenchmarkIntegration` to `test_benchmark.py`. Use `pytest-asyncio` native async test (project uses `asyncio_mode = "auto"`):

```python
@pytest.mark.benchmark
class TestBenchmarkIntegration:
    async def test_pass1_scoring_on_mock_trace(self):
        from tests.benchmark.scoring.checkpoint_scanner import run_pass1
        from tests.benchmark.scenarios.iran_escalation import SCENARIO

        trace = _build_mock_trace()
        pass1 = await run_pass1(SCENARIO, trace, judge_model=None)

        # Mock trace is designed to hit specific checkpoints — assert deterministic values
        assert pass1.checkpoint_hit_rate >= 0.71  # At least 5/7 required checkpoints
        assert pass1.match_accuracy == 1.0         # Both USO long and GLD short should match
        assert pass1.skill_compliance == 1.0        # All expected skills loaded in mock
        assert len(pass1.checkpoints) == 9          # Total checkpoints across 3 layers
```

Build `_build_mock_trace()` helper that creates a 3-layer BenchmarkTrace with:
- **Layer 1:** Effect node with content "High probability of US military strike on Iran" + reasoning about naval positioning and political timing. Skills: geopolitical_risk.
- **Layer 2:** Effect node about oil price increase + Strait of Hormuz. Opportunity node for USO with sentiment_score=85. Skills: supply_chain, geopolitical_risk.
- **Layer 3:** Effect node about inflation from oil/transportation costs, Fed constrained, gold falls. Opportunity node for GLD with sentiment_score=25 (short). Skills: macro_economics.

This mock trace should hit most Iran escalation checkpoints via keyword matching.

- [ ] **Step 2: Run test to verify Pass 1 scoring works**

Run: `cd backend && python -m pytest tests/benchmark/test_benchmark.py::TestBenchmarkIntegration -v -m benchmark`
Expected: PASS — deterministic assertions match mock trace

- [ ] **Step 3: Save mock trace for replay testing**

Add a test that saves the mock trace:
```python
async def test_save_mock_trace(self):
    trace = _build_mock_trace()
    from tests.benchmark.runner import save_trace
    save_trace(trace, "tests/benchmark/traces/iran-escalation/mock_trace.json")
    from tests.benchmark.runner import load_trace
    loaded = load_trace("tests/benchmark/traces/iran-escalation/mock_trace.json")
    assert loaded.scenario_id == "iran-escalation"
```

- [ ] **Step 4: Verify replay mode works with saved trace**

Run: `cd backend && python -m pytest tests/benchmark/test_benchmark.py::TestBenchmark::test_replay_requires_trace -v -m benchmark --mode=replay --trace=tests/benchmark/traces/iran-escalation/mock_trace.json`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/benchmark/test_benchmark.py
git add backend/tests/benchmark/traces/iran-escalation/mock_trace.json
git commit -m "feat(benchmark): add full integration test with mock trace"
```
