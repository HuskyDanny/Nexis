"""Pass 2 LLM judge with CaSE (Causal and Sequential Evidence) context construction.

CaSE principle: each layer is scored using only the context that preceded it —
no hindsight from later layers. This mirrors how the agent actually reasoned.
"""

from __future__ import annotations

import statistics
from typing import Any

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from tests.benchmark.models import (
    AgentTrace,
    BenchmarkTrace,
    ControllerOutput,
    DimensionScore,
    LayerTrace,
    Pass2Scores,
)


# ---------------------------------------------------------------------------
# CaSE input/output builders
# ---------------------------------------------------------------------------


def _summarize_news(news_pool: list[dict]) -> str:
    """Return first 5 news titles joined with '; '."""
    titles = [item.get("title", "") for item in news_pool[:5] if item.get("title")]
    return "; ".join(titles)


def build_judge_input_for_layer(trace: BenchmarkTrace, layer_index: int) -> str:
    """Build CaSE judge input for a given layer.

    Only preceding context is included — no hindsight from current or later layers.
    For layer_index=0, the context contains only the news pool summary.
    """
    parts: list[str] = []

    parts.append(f"Scenario: {trace.scenario_id}")
    parts.append(f"News pool: {_summarize_news(trace.news_pool)}")

    # Include chain summaries ONLY from layers BEFORE this one (no hindsight)
    preceding_layers = trace.layers[:layer_index]
    if preceding_layers:
        parts.append("Prior layer summaries:")
        for layer in preceding_layers:
            parts.append(f"  Layer {layer.layer}: {layer.chain_summary}")

    # Current layer instruction
    current_layer_number = layer_index + 1
    parts.append(
        f"Current layer {current_layer_number}: "
        "Reason about next-order causal effects."
    )

    return "\n".join(parts)


def build_judge_output_for_layer(trace: BenchmarkTrace, layer_index: int) -> str:
    """Build judge output string for a given layer.

    Includes each agent's output_raw, opportunity nodes, and controller reasoning.
    """
    layer = trace.layers[layer_index]
    parts: list[str] = []

    # Agent outputs
    for agent_trace in layer.agents:
        parts.append(f"[{agent_trace.agent}]: {agent_trace.output_raw}")

    # Opportunity nodes only (filter by type=="opportunity")
    opportunity_nodes = [
        node for node in layer.nodes_produced if node.get("type") == "opportunity"
    ]
    if opportunity_nodes:
        parts.append("Opportunity nodes:")
        for node in opportunity_nodes:
            label = node.get("label", node.get("id", str(node)))
            parts.append(f"  - {label}")

    # Controller reasoning
    parts.append(f"Controller reasoning: {layer.controller_output.reasoning}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Dimension metrics
# ---------------------------------------------------------------------------


def create_dimension_metrics(judge_model: Any) -> list[GEval]:
    """Create the 4 GEval dimension metrics for Pass 2 scoring."""
    dimensions = [
        {
            "name": "Reasoning Correctness",
            "criteria": (
                "Evaluate whether the causal logic is valid. "
                "Are the inferred effects plausible given the news context? "
                "Are causal steps correctly ordered and non-contradictory?"
            ),
            "threshold": 0.7,
        },
        {
            "name": "Reasoning Completeness",
            "criteria": (
                "Evaluate whether all important first-order and second-order effects "
                "are captured. Are key causal chains missing? "
                "Does the agent fail to consider obvious downstream effects?"
            ),
            "threshold": 0.6,
        },
        {
            "name": "Match Quality",
            "criteria": (
                "Evaluate whether the financial instruments identified and their "
                "directional calls (long/short, up/down) are well justified "
                "by the reasoning. Are ticker selections appropriate?"
            ),
            "threshold": 0.7,
        },
        {
            "name": "Depth Appropriateness",
            "criteria": (
                "Evaluate whether the controller's stop/continue decision is "
                "well-calibrated. Did it stop too early (missing important effects) "
                "or continue too long (diminishing returns)?"
            ),
            "threshold": 0.6,
        },
    ]

    metrics = []
    for dim in dimensions:
        metric = GEval(
            name=dim["name"],
            criteria=dim["criteria"],
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            model=judge_model,
            threshold=dim["threshold"],
            # GEval always populates .reason after measure()
        )
        metrics.append(metric)

    return metrics


# ---------------------------------------------------------------------------
# Consistency scoring
# ---------------------------------------------------------------------------


def score_with_consistency(
    metric: GEval,
    test_case: LLMTestCase,
    runs: int = 3,
) -> tuple[float, str, list[float]]:
    """Run a metric N times and return (median_score, median_reason, all_scores).

    The median run's reason is returned as the most representative feedback.
    """
    scores: list[float] = []
    reasons: list[str] = []

    for _ in range(runs):
        metric.measure(test_case)
        scores.append(metric.score)
        reasons.append(metric.reason or "")

    median_score = statistics.median(scores)

    # Find the run closest to the median to use as canonical reason
    closest_idx = min(range(len(scores)), key=lambda i: abs(scores[i] - median_score))
    median_reason = reasons[closest_idx]

    return median_score, median_reason, scores


# ---------------------------------------------------------------------------
# run_pass2
# ---------------------------------------------------------------------------


def run_pass2(
    trace: BenchmarkTrace,
    judge_model: Any,
    judge_runs: int = 3,
) -> Pass2Scores:
    """Score each dimension across all layers and compute bonus insights.

    Each dimension is averaged across all layers.
    The worst-scoring layer's reason is surfaced as the most actionable feedback.
    Bonus insights are evaluated on the full trace.
    """
    metrics = create_dimension_metrics(judge_model)
    num_layers = len(trace.layers)

    # Accumulate per-dimension scores and reasons across all layers
    dim_layer_scores: dict[str, list[float]] = {m.name: [] for m in metrics}
    dim_layer_reasons: dict[str, list[str]] = {m.name: [] for m in metrics}
    dim_all_runs: dict[str, list[float]] = {m.name: [] for m in metrics}

    for layer_index in range(num_layers):
        judge_input = build_judge_input_for_layer(trace, layer_index)
        judge_output = build_judge_output_for_layer(trace, layer_index)
        test_case = LLMTestCase(input=judge_input, actual_output=judge_output)

        for metric in metrics:
            score, reason, all_scores = score_with_consistency(
                metric, test_case, runs=judge_runs
            )
            dim_layer_scores[metric.name].append(score)
            dim_layer_reasons[metric.name].append(reason)
            dim_all_runs[metric.name].extend(all_scores)

    # Build DimensionScore: average across layers, worst-layer reason
    dimension_scores: list[DimensionScore] = []
    for metric in metrics:
        layer_scores = dim_layer_scores[metric.name]
        avg_score = statistics.mean(layer_scores) if layer_scores else 0.0
        # Worst-scoring layer gives most actionable feedback
        worst_idx = min(range(len(layer_scores)), key=lambda i: layer_scores[i])
        worst_reason = dim_layer_reasons[metric.name][worst_idx]

        dimension_scores.append(
            DimensionScore(
                name=metric.name,
                score=avg_score,
                reason=worst_reason,
                runs=dim_all_runs[metric.name],
            )
        )

    # Bonus insights: evaluate full-trace context
    bonus_insights = _score_bonus_insights(trace, judge_model)
    bonus_score = (
        len(bonus_insights) * 0.05
    )  # 0.05 per surfaced insight, capped downstream

    return Pass2Scores(
        dimensions=dimension_scores,
        bonus_insights=bonus_insights,
        bonus_score=min(bonus_score, 0.2),  # cap at 0.2
    )


def _score_bonus_insights(trace: BenchmarkTrace, judge_model: Any) -> list[str]:
    """Evaluate the full trace for cross-layer insights that add qualitative value."""
    full_input = "\n\n".join(
        build_judge_input_for_layer(trace, i) for i in range(len(trace.layers))
    )
    full_output = "\n\n".join(
        build_judge_output_for_layer(trace, i) for i in range(len(trace.layers))
    )

    insight_metric = GEval(
        name="Bonus Insights",
        criteria=(
            "Identify any notable strengths in the agent's reasoning across all layers: "
            "cross-layer compounding effects spotted, non-obvious second-order effects, "
            "or particularly well-justified instrument selections. "
            "List each as a short bullet point. Return empty string if none."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=judge_model,
    )

    test_case = LLMTestCase(input=full_input, actual_output=full_output)
    insight_metric.measure(test_case)
    reason = insight_metric.reason or ""

    # Parse bullet lines from reason
    insights = [
        line.strip().lstrip("-•* ").strip()
        for line in reason.splitlines()
        if line.strip() and not line.strip().lower().startswith("the agent")
    ]
    return [ins for ins in insights if ins]


# ---------------------------------------------------------------------------
# Test helper
# ---------------------------------------------------------------------------


def _make_trace() -> BenchmarkTrace:
    """Build a minimal 2-layer BenchmarkTrace for testing."""
    layers = [
        LayerTrace(
            layer=1,
            agents=[
                AgentTrace(
                    agent="causal_agent",
                    input_summary="Iran military escalation news",
                    output_raw="Military strike is likely; oil supply disruption expected.",
                )
            ],
            nodes_produced=[
                {"id": "n1", "type": "causal", "label": "Military escalation"},
                {"id": "n2", "type": "opportunity", "label": "Long XOM"},
            ],
            edges_produced=[{"source": "n1", "target": "n2"}],
            chain_summary="Military strike is likely; geopolitical risk elevated.",
            controller_output=ControllerOutput(
                **{
                    "continue": True,
                    "reasoning": "First-order effects identified; need second-order analysis.",
                    "summary": "Military strike is likely; geopolitical risk elevated.",
                }
            ),
        ),
        LayerTrace(
            layer=2,
            agents=[
                AgentTrace(
                    agent="causal_agent",
                    input_summary="Oil supply disruption effect",
                    output_raw="Oil prices will spike; energy stocks benefit.",
                )
            ],
            nodes_produced=[
                {"id": "n3", "type": "causal", "label": "Oil supply disruption"},
                {"id": "n4", "type": "opportunity", "label": "Long USO"},
            ],
            edges_produced=[{"source": "n3", "target": "n4"}],
            chain_summary="Oil prices will spike; energy sector outperforms.",
            controller_output=ControllerOutput(
                **{
                    "continue": False,
                    "reasoning": "Second-order effects captured; stopping.",
                    "summary": "Oil prices will spike; energy sector outperforms.",
                }
            ),
        ),
    ]

    return BenchmarkTrace(
        scenario_id="iran_escalation_test",
        run_id="test_run_001",
        timestamp="2026-03-23T00:00:00",
        model="test-model",
        total_layers=2,
        layers=layers,
        news_pool=[
            {"title": "Iran military strike imminent", "source": "Reuters"},
            {
                "title": "Oil futures surge on geopolitical tensions",
                "source": "Bloomberg",
            },
        ],
        value_pool=[],
        total_tokens=500,
        total_latency_ms=2000.0,
    )
