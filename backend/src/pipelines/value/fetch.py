"""Value fetching — Yahoo Finance via data_sources."""

import asyncio

from src.core.logger import get_logger

log = get_logger("pipelines.value.fetch")


class YahooFinanceFetch:
    """Fetch value stocks from Yahoo Finance via the existing data_sources helper."""

    async def fetch(self, market: str | None) -> list[dict]:
        from src.services.data_sources import fetch_real_stocks

        log.info("YahooFinanceFetch.fetch(market=%s)", market)
        stocks = await asyncio.to_thread(fetch_real_stocks)
        log.info("YahooFinanceFetch: %d stocks fetched", len(stocks))
        return stocks
