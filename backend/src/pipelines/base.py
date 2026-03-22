from datetime import datetime, timezone, timedelta
from src.models.pool_common import PipelineResult, ScoreResult


class ThresholdRetain:
    def __init__(self, min_score: float, max_age_days: int | None = None):
        self.min_score = min_score
        self.max_age_days = max_age_days

    def should_retain(self, entity: dict) -> bool:
        if entity.get("score", 0) < self.min_score:
            return False
        if self.max_age_days is not None:
            last_seen = entity.get("last_seen_at", "")
            dt = (
                datetime.fromisoformat(last_seen)
                if isinstance(last_seen, str)
                else last_seen
            )
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - dt) > timedelta(days=self.max_age_days):
                return False
        return True


class PoolPipeline:
    def __init__(self, fetch, process, score, retain, repo, market: str):
        self.fetch = fetch
        self.process = process
        self.score = score
        self.retain = retain
        self.repo = repo
        self.market = market

    async def run(self) -> PipelineResult:
        result = PipelineResult()
        raw_items = await self.fetch.fetch(self.market)
        existing = await self.repo.get_all(market=self.market, include_stale=True)

        touched: set[str] = set()
        for raw in raw_items:
            pr = await self.process.process(raw, existing)
            sr: ScoreResult = self.score.score(raw)
            entity = {
                **raw,
                "id": pr.entity_id,
                "score": sr.score,
                "score_factors": sr.factors,
                "status": "active",
            }
            await self.repo.upsert(entity)
            touched.add(pr.entity_id)
            if pr.action == "insert":
                result.inserted += 1
            else:
                result.merged += 1

        for entity in existing:
            eid = entity.get("id", "")
            if eid in touched:
                continue
            sr = self.score.score(entity)
            entity["score"] = sr.score
            entity["score_factors"] = sr.factors
            result.rescored += 1
            if not self.retain.should_retain(entity):
                entity["status"] = "stale"
                result.removed += 1
            await self.repo.upsert(entity)

        return result
