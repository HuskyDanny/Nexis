from datetime import datetime, timezone
from pydantic import BaseModel, Field
from src.models.news_entity import EntityStatus


class ValueEntity(BaseModel):
    id: str
    ticker: str
    name: str
    sector: str
    price: float | None = None
    pe_ratio: float | None = None
    market_cap: float | None = None
    cash_flow: float | None = None
    price_change_pct: float | None = None
    score: float = 0.0
    score_factors: dict[str, float] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: EntityStatus = EntityStatus.ACTIVE
    market: str = "US"
