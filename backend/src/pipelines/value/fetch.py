"""Value fetching — Yahoo Finance placeholder."""

from src.core.logger import get_logger

log = get_logger("pipelines.value.fetch")


class YahooFinanceFetch:
    """Placeholder. Returns empty list until Yahoo Finance API integration is available."""

    async def fetch(self, market: str) -> list[dict]:
        log.info("YahooFinanceFetch.fetch(market=%s) — placeholder", market)
        return []
