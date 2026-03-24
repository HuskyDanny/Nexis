"""Agent tool for directed news search during causal reasoning."""

import asyncio
import concurrent.futures

from crewai.tools import BaseTool
from pydantic import Field

from src.core.config import settings
from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.services.perigon import fetch_perigon_news
from src.services.newsapi import fetch_newsapi_everything

log = get_logger("fetch_news_tool")


async def _has_api_budget() -> bool:
    """Check if we have remaining API budget for agent-initiated calls."""
    from datetime import datetime, timezone

    perigon_col = mongodb.get_collection("perigon_usage")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pg_doc = await perigon_col.find_one({"date": today})
    pg_count = pg_doc.get("count", 0) if pg_doc else 0

    na_col = mongodb.get_collection("newsapi_usage")
    na_doc = await na_col.find_one({"date": today})
    na_count = na_doc.get("count", 0) if na_doc else 0

    return (
        pg_count < settings.perigon_agent_daily_cap
        or na_count < settings.newsapi_agent_daily_cap
    )


async def _fallback_text_search(query: str, limit: int = 5) -> list[dict]:
    """Search existing news_entities by text when API budget is exhausted."""
    col = mongodb.get_collection("news_entities")
    words = query.lower().split()[:3]
    regex_pattern = "|".join(words)
    cursor = (
        col.find(
            {
                "canonical_title": {"$regex": regex_pattern, "$options": "i"},
                "status": "active",
            },
            {"_id": 0},
        )
        .sort("score", -1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


class FetchNewsTool(BaseTool):
    name: str = "fetch_news"
    description: str = (
        "Search for news articles on a specific topic to fill information gaps. "
        "Use when you need more evidence about a causal chain. "
        "Returns relevant news items with title, summary, and metadata."
    )
    max_results: int = Field(default=5)

    def _run(self, query: str) -> list[dict]:
        """Sync wrapper for CrewAI compatibility."""
        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.arun(query=query))
                return future.result()
        except RuntimeError:
            return asyncio.run(self.arun(query=query))

    async def arun(self, query: str) -> list[dict]:
        """Async implementation — search Perigon then NewsAPI."""
        if not await _has_api_budget():
            log.info("API budget exhausted, falling back to text search: %s", query)
            return await _fallback_text_search(query, self.max_results)

        results: list[dict] = []

        try:
            perigon_items = await fetch_perigon_news(query=query, size=self.max_results)
            results.extend(perigon_items)
        except Exception as e:
            log.warning("Perigon fetch failed in tool: %s", e)

        if len(results) < self.max_results:
            try:
                newsapi_items = await fetch_newsapi_everything(
                    query=query,
                    sort_by="relevancy",
                    page_size=self.max_results - len(results),
                )
                results.extend(newsapi_items)
            except Exception as e:
                log.warning("NewsAPI fetch failed in tool: %s", e)

        log.info("fetch_news tool: %d results for '%s'", len(results), query)
        return results[: self.max_results]
