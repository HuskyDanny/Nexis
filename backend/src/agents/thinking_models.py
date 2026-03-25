"""Pydantic output models for CrewAI Task output_json.

CrewAI enforces structured JSON output when a Task has output_json set
to a Pydantic model. This eliminates manual JSON parsing and "Return
ONLY valid JSON" prompt hacks.
"""

from pydantic import BaseModel, Field


class Effect(BaseModel):
    content: str
    reasoning: str
    confidence: int = 50
    parent_ids: list[str] = Field(default_factory=list)
    sector: str = ""
    fetched_news_ids: list[str] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)


class ThinkerOutput(BaseModel):
    effects: list[Effect] = Field(default_factory=list)


class Match(BaseModel):
    ticker: str
    effect_id: str = ""
    sentiment_score: float = 50.0
    agreement_score: float = 50.0
    reasoning: str = ""


class MatcherOutput(BaseModel):
    matches: list[Match] = Field(default_factory=list)


class ControllerOutput(BaseModel):
    continue_decision: bool = Field(False, alias="continue")
    reasoning: str = ""
    summary: str = ""

    model_config = {"populate_by_name": True}
