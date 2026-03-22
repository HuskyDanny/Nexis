### Task 6: Cron Scheduler + Jobs

**Parent:** [Session & Pool Pipeline Plan](../2026-03-22-session-pool-entity-pipeline.md)

**Files:**
- Create: `backend/src/cron/scheduler.py`, `backend/src/cron/__init__.py`
- Create: `backend/tests/cron/test_scheduler.py`
- Modify: `backend/src/core/config.py` (add PoolConfig fields)
- Depends on: Task 3 (PoolPipeline), Task 4 (news strategies), Task 5 (value strategies), Task 2 (repos)

---

- [ ] **Step 1: Add PoolConfig fields to config.py — write test (RED)**

Create `backend/tests/core/test_config.py`:

```python
from src.core.config import Settings


class TestPoolConfig:
    def test_default_news_cron_interval(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_cron_interval_hours == 2

    def test_default_news_similarity_threshold(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_similarity_threshold == 0.75

    def test_default_news_lexical_weight(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_lexical_weight == 0.4

    def test_default_news_base_half_life(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_base_half_life_hours == 24

    def test_default_news_stale_threshold(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_stale_threshold == 30

    def test_default_news_max_age_days(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_max_age_days == 7

    def test_default_value_stale_threshold(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.value_stale_threshold == 20
```

Run: `cd backend && python -m pytest tests/core/test_config.py -v`
Expected: all 7 tests FAIL with `AttributeError` (fields don't exist yet)

- [ ] **Step 2: Add PoolConfig fields to config.py (GREEN)**

Modify `backend/src/core/config.py` — add these fields to the `Settings` class:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    mongodb_url: str = "mongodb://mongodb:27017/financial_agent_v2"
    redis_url: str = "redis://redis:6379/0"
    secret_key: str = "dev-secret-change-in-production"
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"

    # Pool pipeline config
    news_cron_interval_hours: int = 2
    news_similarity_threshold: float = 0.75
    news_lexical_weight: float = 0.4
    news_base_half_life_hours: int = 24
    news_stale_threshold: int = 30
    news_max_age_days: int = 7
    value_stale_threshold: int = 20

    model_config = {"env_file": ".env.base", "env_file_encoding": "utf-8"}


settings = Settings()
```

Run: `cd backend && python -m pytest tests/core/test_config.py -v`
Expected: all 7 tests PASS

- [ ] **Step 3: Write scheduler factory tests (RED)**

Create `backend/tests/cron/test_scheduler.py`:

```python
import pytest
from src.cron.scheduler import build_news_pipeline, build_value_pipeline
from src.pipelines.base import PoolPipeline


class TestBuildNewsPipeline:
    def test_returns_pool_pipeline(self):
        pipeline = build_news_pipeline()
        assert isinstance(pipeline, PoolPipeline)

    def test_has_fetch_strategy(self):
        pipeline = build_news_pipeline()
        assert hasattr(pipeline.fetch, "fetch")

    def test_has_process_strategy(self):
        pipeline = build_news_pipeline()
        assert hasattr(pipeline.process, "process")

    def test_has_score_strategy(self):
        pipeline = build_news_pipeline()
        assert hasattr(pipeline.score, "score")

    def test_has_retain_strategy(self):
        pipeline = build_news_pipeline()
        assert hasattr(pipeline.retain, "evaluate")


class TestBuildValuePipeline:
    def test_returns_pool_pipeline(self):
        pipeline = build_value_pipeline()
        assert isinstance(pipeline, PoolPipeline)

    def test_has_fetch_strategy(self):
        pipeline = build_value_pipeline()
        assert hasattr(pipeline.fetch, "fetch")

    def test_has_process_strategy(self):
        pipeline = build_value_pipeline()
        assert hasattr(pipeline.process, "process")

    def test_has_score_strategy(self):
        pipeline = build_value_pipeline()
        assert hasattr(pipeline.score, "score")

    def test_has_retain_strategy(self):
        pipeline = build_value_pipeline()
        assert hasattr(pipeline.retain, "evaluate")
```

Run: `cd backend && python -m pytest tests/cron/test_scheduler.py -v`
Expected: all 10 tests FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement scheduler.py (GREEN)**

Create `backend/src/cron/__init__.py`:

```python
```

Create `backend/src/cron/scheduler.py`:

```python
"""Cron scheduler — pipeline factories and run functions."""

from datetime import datetime, timezone

from src.core.config import settings
from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.pipelines.base import PoolPipeline, ThresholdRetain
from src.pipelines.news.fetch import AlphaVantageNewsFetch
from src.pipelines.news.process import HybridSimilarityProcess
from src.pipelines.news.score import NewsDecayScore
from src.pipelines.value.fetch import YahooFinanceFetch
from src.pipelines.value.process import TickerUpsertProcess
from src.pipelines.value.score import BounceBackScore

log = get_logger("cron.scheduler")

MARKETS = ["US", "CN"]


def build_news_pipeline() -> PoolPipeline:
    """Factory: assemble news pipeline from configured strategies."""
    return PoolPipeline(
        fetch=AlphaVantageNewsFetch(),
        process=HybridSimilarityProcess(
            lexical_weight=settings.news_lexical_weight,
            threshold=settings.news_similarity_threshold,
        ),
        score=NewsDecayScore(base_half_life_hours=settings.news_base_half_life_hours),
        retain=ThresholdRetain(min_score=settings.news_stale_threshold),
    )


def build_value_pipeline() -> PoolPipeline:
    """Factory: assemble value pipeline from configured strategies."""
    return PoolPipeline(
        fetch=YahooFinanceFetch(),
        process=TickerUpsertProcess(),
        score=BounceBackScore(),
        retain=ThresholdRetain(min_score=settings.value_stale_threshold),
    )


async def run_news_pipeline() -> None:
    """Run news pipeline for all markets, record PipelineRun to MongoDB."""
    pipeline = build_news_pipeline()
    col = mongodb.get_collection("news_entities")

    for market in MARKETS:
        start = datetime.now(timezone.utc)
        log.info("Running news pipeline for market=%s", market)
        try:
            result = await pipeline.run(market, col)
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            run_doc = {
                "date": start.strftime("%Y-%m-%d"),
                "market": market,
                "pipeline": "news",
                "duration": duration,
                "node_count": result.inserted + result.merged,
                "inserted": result.inserted,
                "merged": result.merged,
                "rescored": result.rescored,
                "error_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            runs_col = mongodb.get_collection("pipeline_runs")
            await runs_col.insert_one(run_doc)
            log.info(
                "News pipeline market=%s done in %.1fs — %d inserted, %d merged, %d rescored",
                market, duration, result.inserted, result.merged, result.rescored,
            )
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            log.error("News pipeline market=%s failed after %.1fs: %s", market, duration, e)
            runs_col = mongodb.get_collection("pipeline_runs")
            await runs_col.insert_one({
                "date": start.strftime("%Y-%m-%d"),
                "market": market,
                "pipeline": "news",
                "duration": duration,
                "node_count": 0,
                "error_count": 1,
                "error": str(e),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })


async def run_value_pipeline() -> None:
    """Run value pipeline for all markets, record PipelineRun to MongoDB."""
    pipeline = build_value_pipeline()
    col = mongodb.get_collection("value_entities")

    for market in MARKETS:
        start = datetime.now(timezone.utc)
        log.info("Running value pipeline for market=%s", market)
        try:
            result = await pipeline.run(market, col)
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            run_doc = {
                "date": start.strftime("%Y-%m-%d"),
                "market": market,
                "pipeline": "value",
                "duration": duration,
                "node_count": result.inserted + result.merged,
                "inserted": result.inserted,
                "merged": result.merged,
                "rescored": result.rescored,
                "error_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            runs_col = mongodb.get_collection("pipeline_runs")
            await runs_col.insert_one(run_doc)
            log.info(
                "Value pipeline market=%s done in %.1fs — %d inserted, %d merged, %d rescored",
                market, duration, result.inserted, result.merged, result.rescored,
            )
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            log.error("Value pipeline market=%s failed after %.1fs: %s", market, duration, e)
            runs_col = mongodb.get_collection("pipeline_runs")
            await runs_col.insert_one({
                "date": start.strftime("%Y-%m-%d"),
                "market": market,
                "pipeline": "value",
                "duration": duration,
                "node_count": 0,
                "error_count": 1,
                "error": str(e),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
```

Run: `cd backend && python -m pytest tests/cron/test_scheduler.py -v`
Expected: all 10 tests PASS

- [ ] **Step 5: Run all tests to verify no regressions**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

Expected: all existing + new tests PASS
