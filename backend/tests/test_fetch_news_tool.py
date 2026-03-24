import pytest
from unittest.mock import AsyncMock, patch
from src.agents.tools.fetch_news import FetchNewsTool


@pytest.mark.asyncio
async def test_fetch_news_returns_results():
    tool = FetchNewsTool()
    with patch(
        "src.agents.tools.fetch_news.fetch_perigon_news", new_callable=AsyncMock
    ) as mock_pg, patch(
        "src.agents.tools.fetch_news._provider_budgets", new_callable=AsyncMock
    ) as mock_budgets:
        mock_budgets.return_value = {"perigon": True, "newsapi": True}
        mock_pg.return_value = [{"id": "pg-123", "title": "Test news", "scope": 4}]
        results = await tool.arun(query="rare earth supply chain")
        assert len(results) == 1
        assert results[0]["id"] == "pg-123"


@pytest.mark.asyncio
async def test_fetch_news_fallback_when_no_budget():
    tool = FetchNewsTool()
    with patch(
        "src.agents.tools.fetch_news._provider_budgets", new_callable=AsyncMock
    ) as mock_budgets, patch(
        "src.agents.tools.fetch_news._fallback_text_search", new_callable=AsyncMock
    ) as mock_search:
        mock_budgets.return_value = {"perigon": False, "newsapi": False}
        mock_search.return_value = [{"id": "cached-1", "title": "Cached result"}]
        results = await tool.arun(query="rare earth")
        assert len(results) == 1
        mock_search.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_news_skips_exhausted_provider():
    """Only calls providers that still have budget."""
    tool = FetchNewsTool()
    with patch(
        "src.agents.tools.fetch_news._provider_budgets", new_callable=AsyncMock
    ) as mock_budgets, patch(
        "src.agents.tools.fetch_news.fetch_perigon_news", new_callable=AsyncMock
    ) as mock_pg, patch(
        "src.agents.tools.fetch_news.fetch_newsapi_everything", new_callable=AsyncMock
    ) as mock_na:
        mock_budgets.return_value = {"perigon": False, "newsapi": True}
        mock_na.return_value = [{"id": "na-1", "title": "NewsAPI result"}]
        results = await tool.arun(query="trade policy")
        mock_pg.assert_not_called()
        mock_na.assert_called_once()
        assert len(results) == 1
