"""Tests for report builder and composite scoring (TDD — RED phase)."""

from __future__ import annotations

import pytest

from tests.benchmark.models import (
    BenchmarkReport,
    DimensionScore,
    Pass1Report,
    Pass2Scores,
)
from tests.benchmark.scoring.report import (
    build_aggregate,
    compute_overall,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pass1(
    checkpoint_hit_rate: float = 1.0,
    match_accuracy: float = 1.0,
    skill_compliance: float = 1.0,
) -> Pass1Report:
    return Pass1Report(
        checkpoints=[],
        checkpoint_hit_rate=checkpoint_hit_rate,
        checkpoint_hit_rate_all=checkpoint_hit_rate,
        matches=[],
        match_accuracy=match_accuracy,
        skills=[],
        skill_compliance=skill_compliance,
        total_tokens=0,
        total_latency_ms=0.0,
        tokens_per_layer=0.0,
        latency_per_layer=0.0,
    )


def _make_pass2(
    reasoning_correctness: float = 1.0,
    reasoning_completeness: float = 1.0,
    match_quality: float = 1.0,
    depth_appropriateness: float = 1.0,
) -> Pass2Scores:
    dims = [
        DimensionScore(
            name="reasoning_correctness", score=reasoning_correctness, reason="test"
        ),
        DimensionScore(
            name="reasoning_completeness", score=reasoning_completeness, reason="test"
        ),
        DimensionScore(name="match_quality", score=match_quality, reason="test"),
        DimensionScore(
            name="depth_appropriateness", score=depth_appropriateness, reason="test"
        ),
    ]
    return Pass2Scores(dimensions=dims, bonus_insights=[], bonus_score=0.0)


def _make_report(overall: float) -> BenchmarkReport:
    """Minimal BenchmarkReport with the given overall_score for aggregate tests."""
    return BenchmarkReport(
        scenario_id="test",
        run_id="r1",
        timestamp="2026-01-01T00:00:00",
        mode="full",
        execution_model="test-model",
        judge_model="judge-model",
        judge_runs=1,
        pass1=_make_pass1(),
        pass2=_make_pass2(),
        overall_score=overall,
        grade="A" if overall >= 0.85 else "B",
    )


# ---------------------------------------------------------------------------
# TestComputeOverall
# ---------------------------------------------------------------------------


class TestComputeOverall:
    def test_perfect_score(self):
        score, grade = compute_overall(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        assert abs(score - 1.0) < 1e-9
        assert grade == "A"

    def test_zero_score(self):
        score, grade = compute_overall(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert abs(score - 0.0) < 1e-9
        assert grade == "F"

    def test_grade_boundaries(self):
        # Produce a target composite by using a single dimension weighted fully —
        # easier: just call compute_overall with all dims equal to the boundary value.
        def _uniform(v):
            return compute_overall(v, v, v, v, v, v, v)

        score_a, grade_a = _uniform(0.85)
        assert grade_a == "A"

        score_b, grade_b = _uniform(0.70)
        assert grade_b == "B"

        score_c, grade_c = _uniform(0.55)
        assert grade_c == "C"

        score_d, grade_d = _uniform(0.40)
        assert grade_d == "D"

        # 0.39 → F  (need to get composite just below 0.40)
        score_f, grade_f = _uniform(0.39)
        assert grade_f == "F"


# ---------------------------------------------------------------------------
# TestBuildAggregate
# ---------------------------------------------------------------------------


class TestBuildAggregate:
    def test_stable_runs(self):
        reports = [_make_report(v) for v in [0.80, 0.82, 0.81]]
        agg = build_aggregate("test_scenario", reports)

        assert agg.scenario_id == "test_scenario"
        assert agg.num_runs == 3
        assert abs(agg.mean_overall - (0.80 + 0.82 + 0.81) / 3) < 1e-6
        assert agg.is_stable is True

    def test_unstable_runs(self):
        reports = [_make_report(v) for v in [0.90, 0.40, 0.70]]
        agg = build_aggregate("test_scenario", reports)

        assert agg.is_stable is False

    def test_aggregate_fields(self):
        reports = [_make_report(v) for v in [0.60, 0.80]]
        agg = build_aggregate("s1", reports)

        assert agg.min_overall == pytest.approx(0.60)
        assert agg.max_overall == pytest.approx(0.80)
        assert agg.num_runs == 2
