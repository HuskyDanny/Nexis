import math
from datetime import datetime, timezone
from src.models.pool_common import ScoreResult


class NewsDecayScore:
    def __init__(self, half_life_days: float = 3.0):
        self.half_life_days = half_life_days

    def score(self, entity: dict) -> ScoreResult:
        freshness = self._freshness(entity)
        source_count = self._source_factor(entity)
        scope_factor = self._scope_factor(entity)
        cluster_factor = self._cluster_factor(entity)
        raw = (
            0.4 * freshness
            + 0.25 * source_count
            + 0.2 * scope_factor
            + 0.15 * cluster_factor
        )
        score = round(raw * 100, 1)
        return ScoreResult(
            score=score,
            factors={
                "freshness": round(freshness, 4),
                "source_count": round(source_count, 4),
                "scope_factor": round(scope_factor, 4),
                "cluster_factor": round(cluster_factor, 4),
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

    def _scope_factor(self, entity: dict) -> float:
        scope = entity.get("scope", 2)
        try:
            scope = max(0, min(5, int(scope)))
        except (TypeError, ValueError):
            scope = 2
        return scope / 5.0

    def _cluster_factor(self, entity: dict) -> float:
        cluster_size = entity.get("story_cluster_size", 0)
        return min(1.0, cluster_size / 20)
