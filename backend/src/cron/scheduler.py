"""Cron scheduler — pipeline factories and run functions."""

from datetime import datetime, timezone

from src.core.config import settings
from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.database.repositories.news_entity_repo import NewsEntityRepo
from src.database.repositories.value_entity_repo import ValueEntityRepo
from src.pipelines.base import PoolPipeline, ThresholdRetain
from src.pipelines.news.fetch import (
    CompositeFetch,
    PerigonStoriesFetch,
    PerigonAllFetch,
    NewsAPIHeadlinesFetch,
)
from src.pipelines.news.process import HybridSimilarityProcess
from src.pipelines.news.score import NewsDecayScore
from src.pipelines.value.fetch import YahooFinanceFetch
from src.pipelines.value.process import TickerUpsertProcess
from src.pipelines.value.score import BounceBackScore

log = get_logger("cron.scheduler")

MARKETS = ["US", "CN"]


def build_news_pipeline(repo: NewsEntityRepo) -> PoolPipeline:
    """Factory: assemble global news pipeline (market-agnostic)."""
    return PoolPipeline(
        fetch=CompositeFetch(
            [PerigonStoriesFetch(), PerigonAllFetch(), NewsAPIHeadlinesFetch()]
        ),
        process=HybridSimilarityProcess(
            similarity_threshold=settings.news_similarity_threshold,
        ),
        score=NewsDecayScore(half_life_days=settings.news_base_half_life_hours / 24.0),
        retain=ThresholdRetain(
            min_score=settings.news_stale_threshold,
            max_age_days=settings.news_max_age_days,
        ),
        repo=repo,
        market=None,
    )


def build_value_pipeline(market: str, repo: ValueEntityRepo) -> PoolPipeline:
    """Factory: assemble value pipeline for a given market and repo."""
    return PoolPipeline(
        fetch=YahooFinanceFetch(),
        process=TickerUpsertProcess(),
        score=BounceBackScore(),
        retain=ThresholdRetain(min_score=settings.value_stale_threshold),
        repo=repo,
        market=market,
    )


async def _record_run(
    runs_col,
    *,
    pipeline: str,
    market: str | None,
    start: datetime,
    duration: float,
    result=None,
    error: str | None = None,
) -> None:
    """Insert a PipelineRun record into MongoDB."""
    doc: dict = {
        "date": start.strftime("%Y-%m-%d"),
        "market": market,
        "pipeline": pipeline,
        "duration": duration,
        "created_at": start.isoformat(),
    }
    if error is not None:
        doc["node_count"] = 0
        doc["error_count"] = 1
        doc["error"] = error
    else:
        doc["node_count"] = result.inserted + result.merged
        doc["inserted"] = result.inserted
        doc["merged"] = result.merged
        doc["rescored"] = result.rescored
        doc["error_count"] = 0
    await runs_col.insert_one(doc)


async def run_news_pipeline() -> None:
    """Run global news pipeline once (market-agnostic), record PipelineRun to MongoDB."""
    news_col = mongodb.get_collection("news_entities")
    runs_col = mongodb.get_collection("pipeline_runs")

    repo = NewsEntityRepo(news_col)
    pipeline = build_news_pipeline(repo=repo)
    start = datetime.now(timezone.utc)
    log.info("Running global news pipeline")
    try:
        result = await pipeline.run()
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        await _record_run(
            runs_col,
            pipeline="news",
            market=None,
            start=start,
            duration=duration,
            result=result,
        )
        log.info(
            "News pipeline done in %.1fs — %d inserted, %d merged, %d rescored",
            duration,
            result.inserted,
            result.merged,
            result.rescored,
        )

        # Sync active articles to pools cache so /pools/live gets a cache HIT
        active_articles = await repo.get_active()
        if active_articles:
            pools_col = mongodb.get_collection("pools")
            today = start.strftime("%Y-%m-%d")
            for market in [None, "US", "CN"]:
                await pools_col.update_one(
                    {"type": "news", "date": today, "market": market or "US"},
                    {
                        "$set": {
                            "items": active_articles,
                            "cached_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                    upsert=True,
                )
            log.info("Synced %d news articles to pools cache", len(active_articles))

        # Fire-and-forget graph write for active news entities (graceful degradation)
        from src.graph.writer import try_ingest_news_batch

        try_ingest_news_batch(active_articles)
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        log.error("News pipeline failed after %.1fs: %s", duration, e)
        await _record_run(
            runs_col,
            pipeline="news",
            market=None,
            start=start,
            duration=duration,
            error=str(e),
        )


async def run_value_pipeline() -> None:
    """Run value pipeline for all markets, record PipelineRun to MongoDB."""
    value_col = mongodb.get_collection("value_entities")
    runs_col = mongodb.get_collection("pipeline_runs")

    for market in MARKETS:
        repo = ValueEntityRepo(value_col)
        pipeline = build_value_pipeline(market=market, repo=repo)
        start = datetime.now(timezone.utc)
        log.info("Running value pipeline for market=%s", market)
        try:
            result = await pipeline.run()
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            await runs_col.insert_one(
                {
                    "date": start.strftime("%Y-%m-%d"),
                    "market": market,
                    "pipeline": "value",
                    "duration": duration,
                    "node_count": result.inserted + result.merged,
                    "inserted": result.inserted,
                    "merged": result.merged,
                    "rescored": result.rescored,
                    "error_count": 0,
                    "created_at": start.isoformat(),
                }
            )
            # Sync active values to pools cache
            active_values = await repo.get_active(market=market)
            if active_values:
                pools_col = mongodb.get_collection("pools")
                today = start.strftime("%Y-%m-%d")
                await pools_col.update_one(
                    {"type": "value", "date": today, "market": market},
                    {
                        "$set": {
                            "items": active_values,
                            "cached_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                    upsert=True,
                )
                log.info(
                    "Synced %d value entities to pools cache for market=%s",
                    len(active_values),
                    market,
                )

            log.info(
                "Value pipeline market=%s done in %.1fs — %d inserted, %d merged, %d rescored",
                market,
                duration,
                result.inserted,
                result.merged,
                result.rescored,
            )
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            log.error(
                "Value pipeline market=%s failed after %.1fs: %s", market, duration, e
            )
            await runs_col.insert_one(
                {
                    "date": start.strftime("%Y-%m-%d"),
                    "market": market,
                    "pipeline": "value",
                    "duration": duration,
                    "node_count": 0,
                    "error_count": 1,
                    "error": str(e),
                    "created_at": start.isoformat(),
                }
            )
