### Task 7: Report Builder & Console Printer

**Files:**
- Create: `backend/tests/benchmark/scoring/report.py`
- Test: `backend/tests/benchmark/test_report.py`

- [ ] **Step 1: Write failing tests for report builder**

```python
# backend/tests/benchmark/test_report.py
import pytest
from datetime import datetime, timezone
from tests.benchmark.scoring.report import compute_overall, build_aggregate
from tests.benchmark.models import BenchmarkReport, Pass1Report, Pass2Scores


class TestComputeOverall:
    def test_perfect_score(self):
        score, grade = compute_overall(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        assert score == pytest.approx(1.0) and grade == "A"

    def test_zero_score(self):
        score, grade = compute_overall(0, 0, 0, 0, 0, 0, 0)
        assert score == pytest.approx(0.0) and grade == "F"

    def test_grade_boundaries(self):
        _, g = compute_overall(0.85, 0.85, 0.85, 0.85, 0.85, 0.85, 0.85)
        assert g == "A"
        _, g = compute_overall(0.70, 0.70, 0.70, 0.70, 0.70, 0.70, 0.70)
        assert g == "B"
        _, g = compute_overall(0.55, 0.55, 0.55, 0.55, 0.55, 0.55, 0.55)
        assert g == "C"
        _, g = compute_overall(0.40, 0.40, 0.40, 0.40, 0.40, 0.40, 0.40)
        assert g == "D"
        _, g = compute_overall(0.39, 0.39, 0.39, 0.39, 0.39, 0.39, 0.39)
        assert g == "F"


class TestBuildAggregate:
    def test_stable_runs(self):
        reports = [_make_report(0.80), _make_report(0.82), _make_report(0.81)]
        agg = build_aggregate("test", reports)
        assert agg.is_stable is True and agg.num_runs == 3

    def test_unstable_runs(self):
        reports = [_make_report(0.90), _make_report(0.40), _make_report(0.70)]
        agg = build_aggregate("test", reports)
        assert agg.is_stable is False


def _make_report(overall):
    return BenchmarkReport(
        scenario_id="test", run_id="r", timestamp=datetime.now(timezone.utc),
        mode="replay", execution_model="test", judge_model="test", judge_runs=3,
        overall_score=overall, grade="B",
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/benchmark/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement report builder and console printer**

Create `backend/tests/benchmark/scoring/report.py` with:
- `WEIGHTS` dict — composite score weights (checkpoint_hit_rate: 0.25, match_accuracy: 0.15, skill_compliance: 0.05, reasoning_correctness: 0.20, reasoning_completeness: 0.15, match_quality: 0.10, depth_appropriateness: 0.10)
- `compute_overall(...) -> tuple[float, str]`: weighted sum + grade (A≥0.85, B≥0.70, C≥0.55, D≥0.40, F<0.40)
- `build_report(scenario, trace, pass1, pass2, mode, judge_model_name, judge_runs) -> BenchmarkReport`
- `build_aggregate(scenario_id, reports) -> AggregateReport`: mean, std, min, max, is_stable (std < 0.1)
- `print_report(report) -> None`: formatted console output — checkpoints with method/evidence, matches, skills, LLM judge dimensions with reasons, bonus insights, cost, overall grade
- `print_aggregate(agg) -> None`: mean ± std, range, stability flag

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/benchmark/test_report.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/benchmark/scoring/report.py backend/tests/benchmark/test_report.py
git commit -m "feat(benchmark): add report builder with composite scoring and console printer"
```
