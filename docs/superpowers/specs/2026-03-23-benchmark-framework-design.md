# Benchmark Framework Design — Multi-Agent Causal Reasoning Evaluation

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Evaluation framework for the Nexis multi-agent financial reasoning pipeline

## Overview

A benchmark framework that evaluates how well the Nexis pipeline (Thinker → Matcher → Controller per layer) reasons through multi-layer causal chains from news to investment opportunities. Uses a hybrid approach: deterministic checkpoint scanning + LLM-as-judge scoring, with trace-based replay for cheap iteration.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Evaluation approach | Hybrid: checkpoints + LLM judge | Deterministic rigor on known-good reasoning + nuanced quality from LLM judge |
| Execution model | Trace-based (default) + live on-demand | Separates expensive execution from cheap, iterable scoring |
| Ground truth | Expert-authored checkpoints with directional constraints | Anchors evaluation while allowing LLM judge to catch creative valid paths |
| LLM judge library | DeepEval GEval | Pytest-native, custom criteria, configurable model, structured output, `include_reason` |
| Judge consistency | 3x median scoring | Mitigates non-determinism (research shows ~25% inconsistency in hard cases) |
| Per-layer evaluation | CaSE (Causal Stepwise Evaluation) | Judge sees only preceding context — prevents hindsight bias |
| Checkpoint matching | Keyword fast-path + LLM fallback | Cheap when obvious, intelligent when semantic equivalents differ from keywords |
| Scenario approach | Single deep scenario first | Focus on quality over breadth; template-ize when scenario #2 arrives |
| Test integration | `pytest -m benchmark` marker | Reuses existing pytest infrastructure, excluded from normal test runs |
| Judge model | Configurable (strong for authoritative, cheap for iteration) | Claude Sonnet for real runs, Qwen3-8B for quick checks |

## Evaluation Dimensions (6)

1. **Reasoning correctness** — Is the causal chain logically valid?
2. **Reasoning completeness** — Did it find all important links?
3. **Match quality** — Right instruments, right direction (long/short)?
4. **Skill utilization** — Did agents load appropriate skills per layer?
5. **Latency / cost** — Token usage and wall-clock time per layer
6. **Depth appropriateness** — Did the controller stop at the right depth?

## Scenario Definition

Each scenario is a Python file with a `SCENARIO` dict containing:

```python
SCENARIO = {
    "id": "iran-escalation",
    "name": "Iran Escalation — Oil & Gold",
    "description": "US Navy near Iran + domestic political pressure → military strike → oil spike → inflation → gold down",

    # Inputs
    "news_pool": [
        {"title": "US Navy deploys carrier group near Iranian coast", "sector": "geopolitics", ...},
        {"title": "Domestic political pressure mounts amid massacre fallout", "sector": "politics", ...},
        {"title": "Analysts warn of strategic timing for military action", "sector": "geopolitics", ...},
    ],
    "value_pool": [
        {"ticker": "USO", "name": "United States Oil Fund", "sector": "Energy", ...},
        {"ticker": "XLE", "name": "Energy Select Sector SPDR", "sector": "Energy", ...},
        {"ticker": "GLD", "name": "SPDR Gold Shares", "sector": "Precious Metals", ...},
        {"ticker": "QQQ", "name": "Invesco QQQ Trust", "sector": "Technology", ...},
    ],

    "expected_depth": 3,

    # Directional checkpoints per layer
    "checkpoints": {
        1: [
            {"concept": "military strike / attack on Iran", "required": True},
            {"concept": "political timing — domestic pressure creates window", "required": True},
        ],
        2: [
            {"concept": "oil price increase due to supply disruption", "required": True},
            {"concept": "Iran as major oil exporter or Strait of Hormuz chokepoint", "required": True},
            {"concept": "supply disruption risk to global markets", "required": False},
        ],
        3: [
            {"concept": "inflation increase from oil/transportation costs", "required": True},
            {"concept": "interest rates cannot decrease / Fed constrained", "required": True},
            {"concept": "USD strengthens from tight monetary policy", "required": False},
            {"concept": "gold falls relative to strong USD", "required": True},
        ],
    },

    # Expected matches (instrument + direction)
    "expected_matches": [
        {"ticker": "USO", "direction": "long", "layer": 2, "required": True},
        {"ticker": "GLD", "direction": "short", "layer": 3, "required": True},
    ],

    # Expected skill usage
    "expected_skills": {
        1: ["geopolitical_risk"],
        2: ["supply_chain", "geopolitical_risk"],
        3: ["macro_economics"],
    },
}
```

## Trace Capture & Storage

### Instrumentation Strategy

The benchmark runner operates at the **service layer** (`thinking_service.py`), not the API layer. This avoids MongoDB dependencies and the autouse MongoDB mock in `conftest.py`.

**How trace data is extracted from the existing pipeline:**

1. **Timing:** The runner wraps each `run_thinker()`, `run_matcher()`, `run_controller()` call with `time.perf_counter()` to capture per-agent latency.
2. **Token usage:** CrewAI's `Crew.kickoff()` returns a result object with `token_usage` (prompt_tokens, completion_tokens). The runner extracts this from each crew execution.
3. **Skills loaded:** The `load_skill` CrewAI tool is wrapped with a callback that logs invocations to a list. The runner injects this wrapped tool and collects the skill names after each agent run.
4. **Nodes/edges:** Already returned by `run_thinker()` and `run_matcher()` as dicts.
5. **Controller output:** `run_controller()` returns a full dict `{"continue": bool, "reasoning": str, "summary": str}`. Stored as-is in the trace.

### Trace Models

```python
class AgentTrace(BaseModel):
    agent: str                    # "thinker" | "matcher" | "controller"
    input_summary: str
    output_raw: str
    skills_loaded: list[str]
    tokens_used: int
    latency_ms: int

class ControllerOutput(BaseModel):
    continue_: bool               # Whether to proceed to next layer
    reasoning: str                # Controller's reasoning for the decision
    summary: str                  # Chain summary passed to next layer's thinker

class LayerTrace(BaseModel):
    layer: int
    agents: list[AgentTrace]
    nodes_produced: list[dict]    # ThinkingNode dicts
    edges_produced: list[dict]    # ThinkingEdge dicts
    chain_summary: str            # Controller's summary for next layer
    controller_output: ControllerOutput  # Full controller decision with reasoning

class BenchmarkTrace(BaseModel):
    scenario_id: str
    run_id: str
    timestamp: datetime
    model: str
    total_layers: int
    layers: list[LayerTrace]
    news_pool: list[dict]
    value_pool: list[dict]
    total_tokens: int
    total_latency_ms: int
```

**Note:** `matches_produced` was removed from `LayerTrace` — opportunity nodes are already in `nodes_produced` where `type == "opportunity"`. Filter by type instead of maintaining a redundant field.

### Match Direction Inference

The current pipeline does not produce an explicit `direction` ("long"/"short") on matches. The benchmark infers direction from the matcher's `sentiment_score`:
- `sentiment_score >= 50` → "long" (positive effect on instrument)
- `sentiment_score < 50` → "short" (negative effect on instrument)

This heuristic is documented and clearly marked for replacement when the pipeline adds a native direction field.

### Storage

Traces saved as JSON under `backend/tests/benchmark/traces/<scenario-id>/`. Gitignored.

### Execution Modes

- **Live:** `pytest -m benchmark --mode=live` — runs real pipeline via service layer (bypasses API/MongoDB), captures trace, scores it
- **Replay:** `pytest -m benchmark --mode=replay --trace=<path>` — loads saved trace, scores only (no execution LLM calls)

## Pass 1: Deterministic Checkpoint Scanning

Two-tier system — keyword fast-path + LLM fallback.

### Checkpoint Target Fields

Checkpoints match against the **`content` and `reasoning`** fields of `ThinkingNode` dicts in `nodes_produced`. Both fields are concatenated for matching: `(node["content"] + " " + node["reasoning"]).lower()`.

### Tier 1: Keyword Match (Free, Instant)

Extract key terms from checkpoint concept. If 70%+ term overlap with any node in that layer → hit. Includes directional polarity check using an explicit antonym list: `increase/decrease`, `rise/fall`, `up/down`, `long/short`, `strengthen/weaken`, `grow/shrink`, `expand/contract`, `gain/lose`. If the checkpoint direction term's antonym appears in the node text, `direction_correct = False`.

If the keyword threshold produces ambiguous results (e.g., high term overlap but wrong direction), the checkpoint falls through to Tier 2 rather than marking a false positive.

### Tier 2: LLM Fallback (Cheap, Only When Keywords Miss)

Feeds layer output + checkpoint concept to a cheap judge model. Returns structured verdict: `{present, evidence, direction_correct}`. Catches semantic equivalents that keywords miss (e.g., "export blockade" matching "supply disruption").

### Skill Compliance Semantics

Skill compliance uses **subset checking**: did the agent load *at least* the expected skills? Loading additional skills is acceptable (the agent may reasonably load `sector_rotation` alongside `geopolitical_risk`). Compliance = 1.0 if all expected skills are a subset of actual skills. Partial credit for partial coverage.

### Pass 1 Output

```python
class Pass1Report(BaseModel):
    checkpoints: list[CheckpointResult]   # Each with hit, method, evidence, direction_correct
    checkpoint_hit_rate: float            # Required checkpoints only
    checkpoint_hit_rate_all: float        # Including bonus
    matches: list[MatchResult]            # Ticker + direction correctness
    match_accuracy: float
    skills: list[SkillResult]             # Expected vs actual per layer
    skill_compliance: float
    total_tokens: int
    total_latency_ms: int
    tokens_per_layer: dict[int, int]
    latency_per_layer: dict[int, int]
```

## Pass 2: LLM Judge Scorecard (CaSE)

Uses DeepEval `GEval` with `include_reason=True`. Four scored dimensions + bonus insights.

### Causal Stepwise Evaluation (CaSE)

Each layer is judged using only preceding context — prevents hindsight bias. The preceding context is constructed from `controller_output.summary` at each previous layer (the controller's chain summary). For Layer 1, the context is only the news pool. If the controller stops at a layer, its `summary` from that layer is still available (it's produced as part of the stop decision).

**Note on score overlap:** `checkpoint_hit_rate` (Pass 1) and `reasoning_correctness` (Pass 2) both evaluate reasoning quality, but from different angles. Checkpoints test *recall* of specific expected concepts (did you mention oil?). The LLM judge tests *logical soundness* of the reasoning (is the causal mechanism valid?). Both are needed — an agent can hit all checkpoints with flawed logic, or produce sound reasoning that misses a specific concept.

### Dimensions

```python
GEval(
    name="Reasoning Correctness",
    criteria="Evaluate whether the causal reasoning in this layer is logically sound...",
    include_reason=True,
    model=judge_model,
)
# + Reasoning Completeness, Match Quality, Depth Appropriateness
# + Bonus Insights (full-trace, no threshold)
```

### Judge Consistency

Run each dimension 3x, take median score. Mitigates LLM judge non-determinism.

### Pass 2 Output

```python
class DimensionScore(BaseModel):
    name: str
    score: float        # 0.0-1.0
    reason: str         # Judge's explanation
    runs: list[float]   # All median runs

class Pass2Scores(BaseModel):
    dimensions: list[DimensionScore]
    bonus_insights: list[str]
    bonus_score: float
```

## Scorecard Report

### Composite Scoring

```python
score = (
    checkpoint_hit_rate * 0.25 +
    match_accuracy * 0.15 +
    skill_compliance * 0.05 +
    reasoning_correctness * 0.20 +
    reasoning_completeness * 0.15 +
    match_quality * 0.10 +
    depth_appropriateness * 0.10
)
# Grade: A (≥0.85), B (≥0.70), C (≥0.55), D (≥0.40), F (<0.40)
```

### Multi-Run Aggregation

When `--runs=N` is specified, all N reports are aggregated: mean, std, min, max per dimension. Stability flag: `is_stable = std < 0.1`.

### Console Output

Full scorecard with checkpoints (method + evidence), matches, skills, LLM judge scores with reasons, bonus insights, cost breakdown, and overall grade.

## File Layout

```
backend/tests/benchmark/
├── conftest.py                    # Fixtures, CLI options
├── models.py                     # Trace Pydantic models
├── runner.py                     # Pipeline executor → trace
├── scenarios/
│   └── iran_escalation.py        # First scenario
├── scoring/
│   ├── checkpoint_scanner.py     # Pass 1: keyword + LLM fallback
│   ├── llm_judge.py              # Pass 2: GEval + CaSE
│   ├── report.py                 # Reports, console printer
│   └── judge_models.py           # Judge model factory
├── traces/                       # Saved traces (gitignored)
└── test_benchmark.py             # Pytest entry point
```

## CLI Usage

```bash
# Normal tests (benchmark excluded)
pytest -v

# Quick replay with cheap judge
pytest -m benchmark --mode=replay --trace=traces/iran-escalation/latest.json --judge=qwen3-8b

# Authoritative live run
pytest -m benchmark --mode=live --judge=claude-sonnet-4-6 --runs=3

# Post-refactor regression check
pytest -m benchmark --mode=live --runs=5
```

## Edge Cases

- **Empty layer (no effects found):** Thinker produces 0 nodes → checkpoint hit rate = 0% for that layer. LLM judge scores reasoning completeness low. Not a framework error — it's a valid (bad) pipeline result.
- **Agent timeout:** If an agent times out mid-layer, the runner captures partial output (whatever was returned before timeout). `AgentTrace.output_raw` = partial response. The layer is still scored — missing output = missing checkpoints.
- **Controller stops at Layer 1:** Valid. Only Layer 1 is scored. Depth appropriateness judge evaluates whether stopping was premature given the scenario complexity.
- **No matches at any layer:** `match_accuracy` = 0/N. The benchmark reports this without failing — it's data about pipeline quality, not a framework bug.
- **Replay with outdated trace:** Trace format is versioned (add `trace_version: int` field). If the trace format changes, replay fails fast with a clear version mismatch error.

## Judge Model Factory

The `judge_models.py` factory maps CLI `--judge` values to DeepEval model instances:

```python
def create_judge_model(model_name: str) -> DeepEvalBaseLLM:
    """Map CLI model name to DeepEval model instance.
    Uses LiteLLM under the hood for SiliconFlow models."""
    MODELS = {
        "claude-sonnet-4-6": lambda: AnthropicModel(model="claude-sonnet-4-6"),
        "gpt-4o": lambda: GPTModel(model="gpt-4o"),
        "qwen3-8b": lambda: SiliconFlowModel(model="Qwen/Qwen3-8B"),  # Custom DeepEvalBaseLLM wrapping LiteLLM
        "minimax-m2.5": lambda: SiliconFlowModel(model="MiniMax/MiniMax-M1-80k"),
    }
    if model_name not in MODELS:
        raise ValueError(f"Unknown judge model: {model_name}. Available: {list(MODELS.keys())}")
    return MODELS[model_name]()
```

`SiliconFlowModel` extends `DeepEvalBaseLLM` and delegates to LiteLLM (already in the project for CrewAI).

## Dependencies

- **DeepEval** — GEval, LLMTestCase, configurable models (AnthropicModel, DeepEvalBaseLLM)
- **pytest** — existing infrastructure, marker system, CLI options
- **Pydantic** — trace and report models (already in project)

## Cross-Validation Notes

Design validated against current research:

- **Judge non-determinism:** [Research](https://arxiv.org/html/2512.16041v1) shows ~25% inconsistency in hard cases → mitigated by 3x median
- **Semantic vs causal matching:** [CausalFlip](https://arxiv.org/html/2602.20094) warns LLMs match semantics not causality → checkpoints include direction
- **Context shift vulnerability:** [EconCausal](https://arxiv.org/abs/2510.07231) shows 32.6% accuracy drop under context shifts → CaSE scoring anchors per-layer
- **Framework choice:** DeepEval confirmed as best fit after evaluating MultiAgentBench, AgentBench, GAIA, Ragas, Judgeval, TruLens, Opik, Braintrust, LangSmith
