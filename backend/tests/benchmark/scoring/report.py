"""Report builder, composite scorer, and console printer for benchmark runs."""

from __future__ import annotations

import statistics

from tests.benchmark.models import (
    AggregateReport,
    BenchmarkReport,
    BenchmarkTrace,
    DimensionScore,
    Pass1Report,
    Pass2Scores,
)

# ---------------------------------------------------------------------------
# Composite score weights (must sum to 1.0)
# ---------------------------------------------------------------------------

WEIGHTS: dict[str, float] = {
    "checkpoint_hit_rate": 0.25,
    "match_accuracy": 0.20,
    "skill_compliance": 0.00,  # excluded: structurally always 100% with pre-loaded skills
    "reasoning_correctness": 0.20,
    "reasoning_completeness": 0.15,
    "match_quality": 0.10,
    "depth_appropriateness": 0.10,
}


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def _grade(score: float) -> str:
    if score >= 0.85:
        return "A"
    if score >= 0.70:
        return "B"
    if score >= 0.55:
        return "C"
    if score >= 0.40:
        return "D"
    return "F"


def compute_overall(
    checkpoint_hit_rate: float,
    match_accuracy: float,
    skill_compliance: float,
    reasoning_correctness: float,
    reasoning_completeness: float,
    match_quality: float,
    depth_appropriateness: float,
) -> tuple[float, str]:
    """Return (weighted_score, grade) from individual dimension scores.

    When Pass 2 dimensions are all 0 (not run), the score is re-weighted
    to use only Pass 1 dimensions so the grade reflects actual coverage.
    """
    dimensions = {
        "checkpoint_hit_rate": checkpoint_hit_rate,
        "match_accuracy": match_accuracy,
        "skill_compliance": skill_compliance,
        "reasoning_correctness": reasoning_correctness,
        "reasoning_completeness": reasoning_completeness,
        "match_quality": match_quality,
        "depth_appropriateness": depth_appropriateness,
    }

    # Check if Pass 2 was actually run (any non-zero LLM judge dimension)
    pass2_keys = {
        "reasoning_correctness",
        "reasoning_completeness",
        "match_quality",
        "depth_appropriateness",
    }
    pass2_ran = any(dimensions[k] > 0 for k in pass2_keys)

    score = sum(WEIGHTS[k] * dimensions[k] for k in dimensions)

    if not pass2_ran:
        # Cap grade at C when Pass 2 is absent — surface-level checks alone
        # cannot earn above C regardless of how perfect they are.
        grade = _grade(score)
        if grade in ("A", "B"):
            grade = "C*"  # asterisk signals incomplete evaluation
        return round(score, 10), grade

    return round(score, 10), _grade(round(score, 10))


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------


def build_report(
    scenario,
    trace: BenchmarkTrace,
    pass1: Pass1Report,
    pass2: Pass2Scores,
    mode: str,
    judge_model_name: str,
    judge_runs: int,
) -> BenchmarkReport:
    """Combine pass1 + pass2 results into a full BenchmarkReport."""
    dim_by_name: dict[str, float] = {d.name: d.score for d in pass2.dimensions}

    overall, grade = compute_overall(
        checkpoint_hit_rate=pass1.checkpoint_hit_rate,
        match_accuracy=pass1.match_accuracy,
        skill_compliance=pass1.skill_compliance,
        reasoning_correctness=dim_by_name.get("Reasoning Correctness", 0.0),
        reasoning_completeness=dim_by_name.get("Reasoning Completeness", 0.0),
        match_quality=dim_by_name.get("Match Quality", 0.0),
        depth_appropriateness=dim_by_name.get("Depth Appropriateness", 0.0),
    )

    return BenchmarkReport(
        scenario_id=trace.scenario_id,
        run_id=trace.run_id,
        timestamp=trace.timestamp,
        mode=mode,
        execution_model=trace.model,
        judge_model=judge_model_name,
        judge_runs=judge_runs,
        pass1=pass1,
        pass2=pass2,
        overall_score=overall,
        grade=grade,
    )


def build_aggregate(
    scenario_id: str, reports: list[BenchmarkReport]
) -> AggregateReport:
    """Compute aggregate statistics across multiple runs of the same scenario."""
    scores = [r.overall_score for r in reports]
    mean = statistics.mean(scores)
    std = statistics.stdev(scores) if len(scores) > 1 else 0.0
    return AggregateReport(
        scenario_id=scenario_id,
        num_runs=len(reports),
        reports=reports,
        mean_overall=mean,
        std_overall=std,
        min_overall=min(scores),
        max_overall=max(scores),
        is_stable=std < 0.1,
    )


# ---------------------------------------------------------------------------
# Console printers
# ---------------------------------------------------------------------------


def print_report(report: BenchmarkReport) -> None:
    """Print a formatted benchmark report to the console."""
    p1 = report.pass1
    p2 = report.pass2

    _sep = "=" * 70

    print(_sep)
    print(f"  BENCHMARK REPORT  |  {report.scenario_id}  |  run {report.run_id}")
    print(_sep)
    print(f"  Mode           : {report.mode}")
    print(f"  Execution model: {report.execution_model}")
    print(f"  Judge model    : {report.judge_model}  (x{report.judge_runs} runs)")
    print(f"  Timestamp      : {report.timestamp}")
    print()

    # --- Checkpoints ---
    print("  CHECKPOINTS")
    print(f"  Hit rate (required): {p1.checkpoint_hit_rate:.2%}")
    print(f"  Hit rate (all)     : {p1.checkpoint_hit_rate_all:.2%}")
    for cp in p1.checkpoints:
        status = "HIT " if cp.hit else "MISS"
        req = "[req]" if cp.required else "[opt]"
        print(
            f"    [{status}] {req} L{cp.layer:02d}  {cp.concept}"
            f"  method={cp.method}  evidence={cp.evidence!r}"
        )
    print()

    # --- Matches ---
    print("  STOCK MATCHES")
    print(f"  Accuracy: {p1.match_accuracy:.2%}")
    for m in p1.matches:
        status = "OK  " if m.correct else "FAIL"
        found_dir = m.actual_direction or "—"
        print(
            f"    [{status}] {m.ticker:<6s}  expected={m.expected_direction:<5s}"
            f"  actual={found_dir}"
        )
    print()

    # --- Skills ---
    print("  SKILL COMPLIANCE")
    print(f"  Compliance: {p1.skill_compliance:.2%}")
    for sk in p1.skills:
        status = "OK  " if sk.all_loaded else "FAIL"
        missing = set(sk.expected_skills) - set(sk.actual_skills)
        print(
            f"    [{status}] L{sk.layer:02d}  expected={sk.expected_skills}"
            f"  actual={sk.actual_skills}"
            + (f"  missing={list(missing)}" if missing else "")
        )
    print()

    # --- LLM judge dimensions ---
    print("  LLM JUDGE DIMENSIONS")
    for dim in p2.dimensions:
        bar = int(dim.score * 20) * "█"
        print(f"    {dim.name:<28s}  {dim.score:.2f}  {bar}")
        print(f"      reason: {dim.reason}")
        if dim.runs:
            runs_str = ", ".join(f"{v:.2f}" for v in dim.runs)
            print(f"      runs  : [{runs_str}]")
    print()

    # --- Bonus insights ---
    if p2.bonus_insights:
        print("  BONUS INSIGHTS")
        for insight in p2.bonus_insights:
            print(f"    • {insight}")
        print(f"  Bonus score: {p2.bonus_score:.2f}")
        print()

    # --- Cost / performance ---
    print("  COST & PERFORMANCE")
    print(f"  Total tokens      : {p1.total_tokens:,}")
    print(f"  Total latency     : {p1.total_latency_ms:.0f} ms")
    print(f"  Tokens / layer    : {p1.tokens_per_layer:.1f}")
    print(f"  Latency / layer   : {p1.latency_per_layer:.1f} ms")
    print()

    # --- Overall ---
    print(_sep)
    print(f"  OVERALL SCORE: {report.overall_score:.4f}   GRADE: {report.grade}")
    print(_sep)
    print()


def print_aggregate(agg: AggregateReport) -> None:
    """Print aggregate statistics across multiple runs."""
    _sep = "-" * 50

    print(_sep)
    print(f"  AGGREGATE  |  {agg.scenario_id}  ({agg.num_runs} runs)")
    print(_sep)
    print(f"  Mean  : {agg.mean_overall:.4f}  ±  {agg.std_overall:.4f}")
    print(f"  Range : {agg.min_overall:.4f}  –  {agg.max_overall:.4f}")
    stability = "STABLE" if agg.is_stable else "UNSTABLE"
    print(f"  Stability: {stability}  (std {'<' if agg.is_stable else '>='} 0.10)")
    print(_sep)
    print()
