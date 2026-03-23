import math
from datetime import datetime, timezone
from src.models.pool_common import ScoreResult


class NewsDecayScore:
    def __init__(self, half_life_days: float = 3.0):
        self.half_life_days = half_life_days

    def score(self, entity: dict) -> ScoreResult:
        freshness = self._freshness(entity)
        source_count = self._source_factor(entity)
        ticker_relevance = self._ticker_factor(entity)
        raw = 0.5 * freshness + 0.3 * source_count + 0.2 * ticker_relevance
        score = round(raw * 100, 1)  # Normalize to 0–100 scale
        return ScoreResult(
            score=score,
            factors={
                "freshness": round(freshness, 4),
                "source_count": round(source_count, 4),
                "ticker_relevance": round(ticker_relevance, 4),
            },
        )

    def _freshness(self, entity: dict) -> float:
        last_seen = entity.get("last_seen_at", "")
        if not last_seen:
            return 0.0
        dt = (
            datetime.fromisoformat(last_seen)
            if isinstance(last_seen, str)
            else last_seen
        )
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
        return math.pow(0.5, age_days / self.half_life_days)

    def _source_factor(self, entity: dict) -> float:
        count = len(entity.get("sources", []))
        return min(1.0, 0.2 + 0.2 * count) if count else 0.0

    def _ticker_factor(self, entity: dict) -> float:
        count = len(entity.get("tickers", []))
        return min(1.0, 0.3 * count) if count else 0.0
