"""Cron scheduler — pipeline factories and run functions."""

from datetime import datetime, timezone

from src.core.config import settings
from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.database.repositories.news_entity_repo import NewsEntityRepo
from src.database.repositories.value_entity_repo import ValueEntityRepo
from src.pipelines.base import PoolPipeline, ThresholdRetain
from src.pipelines.news.fetch import AlphaVantageNewsFetch
from src.pipelines.news.process import HybridSimilarityProcess
from src.pipelines.news.score import NewsDecayScore
from src.pipelines.value.fetch import YahooFinanceFetch
from src.pipelines.value.process import TickerUpsertProcess
from src.pipelines.value.score import BounceBackScore

log = get_logger("cron.scheduler")

MARKETS = ["US", "CN"]


def build_news_pipeline(market: str, repo: NewsEntityRepo) -> PoolPipeline:
    """Factory: assemble news pipeline for a given market and repo."""
    return PoolPipeline(
        fetch=AlphaVantageNewsFetch(),
        process=HybridSimilarityProcess(
            title_threshold=settings.news_similarity_threshold,
            entity_threshold=settings.news_similarity_threshold,
        ),
        score=NewsDecayScore(half_life_days=settings.news_base_half_life_hours / 24.0),
        retain=ThresholdRetain(
            min_score=settings.news_stale_threshold,
            max_age_days=settings.news_max_age_days,
        ),
        repo=repo,
        market=market,
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


async def run_news_pipeline() -> None:
    """Run news pipeline for all markets, record PipelineRun to MongoDB."""
    news_col = mongodb.get_collection("news_entities")
    runs_col = mongodb.get_collection("pipeline_runs")

    for market in MARKETS:
        repo = NewsEntityRepo(news_col)
        pipeline = build_news_pipeline(market=market, repo=repo)
        start = datetime.now(timezone.utc)
        log.info("Running news pipeline for market=%s", market)
        try:
            result = await pipeline.run()
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            await runs_col.insert_one(
                {
                    "date": start.strftime("%Y-%m-%d"),
                    "market": market,
                    "pipeline": "news",
                    "duration": duration,
                    "node_count": result.inserted + result.merged,
                    "inserted": result.inserted,
                    "merged": result.merged,
                    "rescored": result.rescored,
                    "error_count": 0,
                    "created_at": start.isoformat(),
                }
            )
            log.info(
                "News pipeline market=%s done in %.1fs — %d inserted, %d merged, %d rescored",
                market,
                duration,
                result.inserted,
                result.merged,
                result.rescored,
            )
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            log.error(
                "News pipeline market=%s failed after %.1fs: %s", market, duration, e
            )
            await runs_col.insert_one(
                {
                    "date": start.strftime("%Y-%m-%d"),
                    "market": market,
                    "pipeline": "news",
                    "duration": duration,
                    "node_count": 0,
                    "error_count": 1,
                    "error": str(e),
                    "created_at": start.isoformat(),
                }
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
