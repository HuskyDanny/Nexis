# Benchmark Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a benchmark framework that evaluates the Nexis multi-agent pipeline's causal reasoning quality using hybrid checkpoint scanning + LLM-as-judge scoring.

**Architecture:** Trace-based evaluation — the runner executes the pipeline and captures a full trace (per-agent inputs/outputs/timing/skills per layer), then two scoring passes evaluate the trace: Pass 1 (deterministic checkpoints with LLM fallback) and Pass 2 (DeepEval GEval LLM judge with CaSE). Results are combined into a graded scorecard.

**Tech Stack:** pytest (marker-based), DeepEval (GEval, AnthropicModel, DeepEvalBaseLLM), Pydantic v2, existing CrewAI pipeline

**Spec:** `docs/superpowers/specs/2026-03-23-benchmark-framework-design.md`

---

## File Structure

```
backend/tests/benchmark/
├── __init__.py
├── conftest.py              # pytest CLI options (--mode, --judge, --runs, --trace), fixtures
├── models.py                # BenchmarkTrace, LayerTrace, AgentTrace, ControllerOutput, report models
├── runner.py                # Wraps run_layer() with timing/token/skill instrumentation → BenchmarkTrace
├── scenarios/
│   ├── __init__.py
│   └── iran_escalation.py   # SCENARIO dict with news, values, checkpoints, matches, skills
├── scoring/
│   ├── __init__.py
│   ├── checkpoint_scanner.py # Pass 1: keyword + LLM fallback checkpoint matching
│   ├── llm_judge.py         # Pass 2: GEval dimensions with CaSE context construction
│   ├── judge_models.py      # Factory: CLI model name → DeepEval model instance
│   └── report.py            # BenchmarkReport, AggregateReport, composite score, console printer
├── traces/                  # Saved trace JSON files (gitignored)
│   └── .gitkeep
└── test_benchmark.py        # Pytest entry point, @pytest.mark.benchmark
```

---

## Dependencies

Tasks 3→4 must be sequential (`scoring/__init__.py` created in Task 3). Tasks 4-5 require DeepEval (Task 1). All other tasks within 2-7 can be parallelized.

**MongoDB mock note:** The root `tests/conftest.py` has an `autouse=True` MongoDB mock. This applies to benchmark tests too. In replay mode this is harmless (no DB calls). In live mode, `run_layer()` may call DB-dependent code — the benchmark conftest in Task 8 should override the autouse fixture if needed, or the runner should be designed to avoid any DB-touching paths.

## Tasks

| # | Task | Files | Deliverable |
|---|------|-------|-------------|
| 1 | [[benchmark-framework/task-1-dependencies]] | pyproject.toml | Install DeepEval + benchmark marker |
| 2 | [[benchmark-framework/task-2-models]] | models.py | Trace + report Pydantic models |
| 3 | [[benchmark-framework/task-3-scenario]] | scenarios/iran_escalation.py | First benchmark scenario |
| 4 | [[benchmark-framework/task-4-checkpoint-scanner]] | scoring/checkpoint_scanner.py | Pass 1: keyword + LLM fallback |
| 5 | [[benchmark-framework/task-5-judge-models]] | scoring/judge_models.py | Configurable judge model factory |
| 6 | [[benchmark-framework/task-6-llm-judge]] | scoring/llm_judge.py | Pass 2: GEval + CaSE |
| 7 | [[benchmark-framework/task-7-report]] | scoring/report.py | Composite scoring + console output |
| 8 | [[benchmark-framework/task-8-runner]] | runner.py | Instrumented pipeline executor |
| 9 | [[benchmark-framework/task-9-pytest-config]] | conftest.py, test_benchmark.py | CLI options + entry point |
| 10 | [[benchmark-framework/task-10-integration]] | test_benchmark.py | Full scoring on mock trace |
