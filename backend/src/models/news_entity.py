from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, Field


class EntityStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"


class NewsEntity(BaseModel):
    id: str
    canonical_title: str
    summary: str
    sources: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    named_entities: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)
    score: float = 0.0
    score_factors: dict[str, float] = Field(default_factory=dict)
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: EntityStatus = EntityStatus.ACTIVE
    market: str = "US"
