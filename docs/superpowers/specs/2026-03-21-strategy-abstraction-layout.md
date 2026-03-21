# Strategy Abstraction & File Layout

**Parent:** [Design Spec](2026-03-21-session-lifecycle-pool-entities-design.md)

## Strategy Interfaces

```python
class FetchStrategy(Protocol):
    async def fetch(self, market: str) -> list[dict]: ...

class ProcessStrategy(Protocol):
    async def process(self, raw: dict, existing: list[dict]) -> ProcessResult: ...

class ScoreStrategy(Protocol):
    def score(self, entity: dict) -> ScoreResult: ...

class RetainStrategy(Protocol):
    def evaluate(self, entity: dict) -> str: ...  # "active" | "stale"
```

## Pipeline Orchestrator

```python
class PoolPipeline:
    def __init__(self, fetch, process, score, retain, repo): ...

    async def run(self, market: str) -> PipelineResult:
        raw_items = await self.fetch.fetch(market)
        existing = await self.repo.get_active(market)
        for item in raw_items:
            result = await self.process.process(item, existing)
            entity = result.merged_entity if result.action == "merge" else result.new_entity
            scored = self.score.score(entity)
            entity["score"] = scored.total
            entity["score_factors"] = scored.factors
            entity["status"] = self.retain.evaluate(entity)
            await self.repo.upsert(entity)
        await self._rescore_existing(market)

    async def _rescore_existing(self, market: str):
        """Re-score entities not touched in this run (decay freshness)."""
        all_active = await self.repo.get_active(market)
        for entity in all_active:
            scored = self.score.score(entity)
            entity["score"] = scored.total
            entity["score_factors"] = scored.factors
            entity["status"] = self.retain.evaluate(entity)
            await self.repo.upsert(entity)
```

## Concrete Wiring

```python
news_pipeline = PoolPipeline(
    fetch   = AlphaVantageNewsFetch(),
    process = HybridSimilarityProcess(lexical_weight=0.4, semantic_weight=0.6, threshold=0.75),
    score   = NewsDecayScore(base_half_life=24),
    retain  = ThresholdRetain(min_score=30),
    repo    = NewsEntityRepo(),
)

value_pipeline = PoolPipeline(
    fetch   = YahooFinanceFetch(),
    process = TickerUpsertProcess(),
    score   = BounceBackScore(weights={...}),
    retain  = ThresholdRetain(min_score=20),
    repo    = ValueEntityRepo(),
)
```

## Config-Driven Parameters

```python
class PoolConfig:
    news_cron_interval_hours: int = 2
    value_cron_schedule: list[str] = ["08:00", "21:00"]
    news_similarity_threshold: float = 0.75
    news_lexical_weight: float = 0.4
    news_base_half_life_hours: int = 24
    news_stale_threshold: float = 30
    value_stale_threshold: float = 20
    bounce_back_weights: dict = {
        "structural_necessity": 0.20,
        "sector_position": 0.15,
        "emotional_discount": 0.20,
        "cash_flow_health": 0.20,
        "trend_alignment": 0.15,
        "macro_tailwind": 0.10,
    }
```

## File Layout

```
backend/src/
├── api/
│   ├── thinking.py              ← updated: use Redis cache
│   ├── pools.py                 ← updated: ?include_stale, entity model
├── core/
│   ├── config.py                ← add PoolConfig
├── database/
│   ├── redis.py                 ← now actually used
│   └── repositories/
│       ├── thinking_repo.py     ← updated: Redis write-aside
│       ├── news_entity_repo.py  ← NEW
│       └── value_entity_repo.py ← NEW
├── models/
│   ├── news_entity.py           ← NEW
│   ├── value_entity.py          ← NEW
│   └── pool_common.py           ← NEW: ScoreResult, ProcessResult, PipelineResult
├── pipelines/
│   ├── base.py                  ← PoolPipeline + strategy protocols
│   ├── news/
│   │   ├── fetch.py             ← AlphaVantageNewsFetch
│   │   ├── process.py           ← HybridSimilarityProcess
│   │   ├── score.py             ← NewsDecayScore
│   │   └── retain.py            ← ThresholdRetain (news config)
│   └── value/
│       ├── fetch.py             ← YahooFinanceFetch
│       ├── process.py           ← TickerUpsertProcess
│       ├── score.py             ← BounceBackScore
│       └── retain.py            ← ThresholdRetain (value config)
├── services/
│   └── session_cache.py         ← NEW: Redis write-aside for sessions
└── cron/
    ├── scheduler.py             ← NEW: cron registration
    ├── news_job.py              ← NEW: wires NewsPipeline
    └── value_job.py             ← NEW: wires ValuePipeline
```

## Key Decisions

- `pipelines/` is separate from `services/` — pipelines are batch/cron, services are request-time
- One file per strategy — small, focused, independently testable
- Shared `ThresholdRetain` lives in `pipelines/base.py` (not duplicated in news/ and value/)
- Config-driven — all tunable numbers in `PoolConfig`, not hardcoded
- `thinking.py` API refactored to use `ThinkingRepo` + `SessionCache` — no more direct collection access
- `version` field added to `ThinkingSession` model for optimistic concurrency
- Redis TTL is configurable via `SessionConfig.cache_ttl_seconds` (default 1800)
- Pools API response changes from `{news: [], value: []}` to `{news_entities: [], value_entities: []}` with scored entity objects
