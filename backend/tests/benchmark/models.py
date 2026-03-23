"""Pydantic models for benchmark traces and reports."""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class AgentTrace(BaseModel):
    """Captures a single agent's execution within a layer."""

    agent: str
    input_summary: str
    output_raw: str
    skills_loaded: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    latency_ms: float = 0.0


class ControllerOutput(BaseModel):
    """Output from the layer controller deciding whether to continue."""

    model_config = {"populate_by_name": True}

    continue_: bool = Field(alias="continue")
    reasoning: str
    summary: str


class LayerTrace(BaseModel):
    """Full trace for a single thinking layer."""

    layer: int
    agents: list[AgentTrace]
    nodes_produced: list[dict]
    edges_produced: list[dict]
    chain_summary: str
    controller_output: ControllerOutput


class BenchmarkTrace(BaseModel):
    """Complete execution trace for one benchmark run."""

    scenario_id: str
    run_id: str
    trace_version: int = 1
    timestamp: str
    model: str
    total_layers: int
    layers: list[LayerTrace]
    news_pool: list[dict]
    value_pool: list[dict]
    total_tokens: int
    total_latency_ms: float


class CheckpointResult(BaseModel):
    """Result of evaluating a single scenario checkpoint."""

    layer: int
    concept: str
    required: bool
    hit: bool
    method: Literal["keyword", "llm"]
    matched_node_id: Optional[str]
    direction_correct: Optional[bool]
    evidence: str


class MatchResult(BaseModel):
    """Result of matching a ticker against expected direction."""

    ticker: str
    expected_direction: str
    found: bool
    actual_direction: Optional[str]
    correct: bool


class SkillResult(BaseModel):
    """Result of verifying skill loading compliance for a layer."""

    layer: int
    expected_skills: list[str]
    actual_skills: list[str]
    all_loaded: bool


class DimensionScore(BaseModel):
    """Score for a single qualitative evaluation dimension."""

    name: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    runs: list[float] = Field(default_factory=list)


class Pass1Report(BaseModel):
    """Deterministic pass 1 evaluation results."""

    checkpoints: list[CheckpointResult]
    checkpoint_hit_rate: float
    checkpoint_hit_rate_all: float
    matches: list[MatchResult]
    match_accuracy: float
    skills: list[SkillResult]
    skill_compliance: float
    total_tokens: int
    total_latency_ms: float
    tokens_per_layer: float
    latency_per_layer: float


class Pass2Scores(BaseModel):
    """LLM-judge pass 2 qualitative evaluation scores."""

    dimensions: list[DimensionScore] = Field(default_factory=list)
    bonus_insights: list[str] = Field(default_factory=list)
    bonus_score: float = 0.0


class BenchmarkReport(BaseModel):
    """Full benchmark report combining pass 1 and pass 2 results."""

    scenario_id: str
    run_id: str
    timestamp: str
    mode: str
    execution_model: str
    judge_model: str
    judge_runs: int
    pass1: Pass1Report
    pass2: Pass2Scores
    overall_score: float
    grade: str


class AggregateReport(BaseModel):
    """Aggregate statistics across multiple benchmark runs."""

    scenario_id: str
    num_runs: int
    reports: list[BenchmarkReport]
    mean_overall: float
    std_overall: float
    min_overall: float
    max_overall: float
    is_stable: bool
