"""Agent tool for directed news search during causal reasoning."""

import asyncio
import concurrent.futures
import re

from crewai.tools import BaseTool
from pydantic import Field

from src.core.config import settings
from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.services.perigon import fetch_perigon_news
from src.services.newsapi import fetch_newsapi_everything

log = get_logger("fetch_news_tool")

_MAX_TOKEN_LEN = 40


async def _provider_budgets() -> dict[str, bool]:
    """Return per-provider budget availability."""
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    perigon_col = mongodb.get_collection("perigon_usage")
    pg_doc = await perigon_col.find_one({"date": today})
    pg_remaining = (pg_doc.get("count", 0) if pg_doc else 0) < settings.perigon_agent_daily_cap

    na_col = mongodb.get_collection("newsapi_usage")
    na_doc = await na_col.find_one({"date": today})
    na_remaining = (na_doc.get("count", 0) if na_doc else 0) < settings.newsapi_agent_daily_cap

    return {"perigon": pg_remaining, "newsapi": na_remaining}


async def _fallback_text_search(query: str, limit: int = 5) -> list[dict]:
    """Search existing news_entities by text when API budget is exhausted."""
    col = mongodb.get_collection("news_entities")
    words = query.lower().split()[:3]
    escaped = [re.escape(w)[:_MAX_TOKEN_LEN] for w in words]
    regex_pattern = "|".join(escaped)
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
        """Async implementation — call only providers that still have budget."""
        budgets = await _provider_budgets()

        if not any(budgets.values()):
            log.info("All API budgets exhausted, falling back to text search: %s", query)
            return await _fallback_text_search(query, self.max_results)

        results: list[dict] = []

        if budgets["perigon"]:
            try:
                perigon_items = await fetch_perigon_news(query=query, size=self.max_results)
                results.extend(perigon_items)
            except Exception as e:
                log.warning("Perigon fetch failed in tool: %s", e)

        if len(results) < self.max_results and budgets["newsapi"]:
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
