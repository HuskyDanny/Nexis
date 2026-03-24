import pytest
from unittest.mock import AsyncMock, patch
from src.agents.tools.fetch_news import FetchNewsTool


@pytest.mark.asyncio
async def test_fetch_news_returns_results():
    tool = FetchNewsTool()
    with patch(
        "src.agents.tools.fetch_news.fetch_perigon_news", new_callable=AsyncMock
    ) as mock_pg, patch(
        "src.agents.tools.fetch_news._has_api_budget", new_callable=AsyncMock
    ) as mock_budget:
        mock_budget.return_value = True
        mock_pg.return_value = [{"id": "pg-123", "title": "Test news", "scope": 4}]
        results = await tool.arun(query="rare earth supply chain")
        assert len(results) == 1
        assert results[0]["id"] == "pg-123"


@pytest.mark.asyncio
async def test_fetch_news_fallback_when_no_budget():
    tool = FetchNewsTool()
    with patch(
        "src.agents.tools.fetch_news._has_api_budget", new_callable=AsyncMock
    ) as mock_budget, patch(
        "src.agents.tools.fetch_news._fallback_text_search", new_callable=AsyncMock
    ) as mock_search:
        mock_budget.return_value = False
        mock_search.return_value = [{"id": "cached-1", "title": "Cached result"}]
        results = await tool.arun(query="rare earth")
        assert len(results) == 1
        mock_search.assert_called_once()
