from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class PipelineRun(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    date: str
    market: str
    duration: float
    node_count: int
    error_count: int = 0
    cost: float = 0.0
    step_scores: dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
