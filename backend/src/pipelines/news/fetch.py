"""News fetch strategies — composite multi-source fetching."""

from src.core.logger import get_logger
from src.services.perigon import fetch_perigon_stories, fetch_perigon_news
from src.services.newsapi import fetch_newsapi_headlines

log = get_logger("news_fetch")


class CompositeFetch:
    """Runs multiple fetch strategies and merges results."""

    def __init__(self, fetchers: list):
        self.fetchers = fetchers

    async def fetch(self, market: str | None = None) -> list[dict]:
        results: list[dict] = []
        for f in self.fetchers:
            try:
                items = await f.fetch(market)
                results.extend(items)
            except Exception as e:
                log.warning("Fetcher %s failed: %s", f.__class__.__name__, e)
        return results


class PerigonStoriesFetch:
    """Fetches clustered macro events from Perigon /stories."""

    async def fetch(self, market: str | None = None) -> list[dict]:
        return await fetch_perigon_stories()


class PerigonAllFetch:
    """Fetches broad news from Perigon /all with broadened categories."""

    async def fetch(self, market: str | None = None) -> list[dict]:
        return await fetch_perigon_news()


class NewsAPIHeadlinesFetch:
    """Fetches breaking headlines from NewsAPI /top-headlines."""

    async def fetch(self, market: str | None = None) -> list[dict]:
        return await fetch_newsapi_headlines()
