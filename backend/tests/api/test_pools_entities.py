import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def _make_cursor(items):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=items)
    return cursor


@pytest.mark.asyncio
async def test_pools_returns_entity_format():
    mock_news = MagicMock()
    mock_value = MagicMock()
    mock_news.find.return_value = _make_cursor(
        [{"id": "abc", "canonical_title": "Test", "score": 80, "status": "active"}]
    )
    mock_value.find.return_value = _make_cursor(
        [{"id": "AAPL:US", "ticker": "AAPL", "score": 65, "status": "active"}]
    )

    def get_col(name):
        return {"news_entities": mock_news, "value_entities": mock_value}.get(
            name, AsyncMock()
        )

    with patch("src.api.pools.mongodb") as mock_db:
        mock_db.get_collection.side_effect = get_col
        from src.api.pools import get_pools

        result = await get_pools("2026-03-22", market="US")
        assert "news_entities" in result
        assert "value_entities" in result
        assert result["news_entities"][0]["id"] == "abc"


@pytest.mark.asyncio
async def test_pools_filters_stale_by_default():
    mock_news = MagicMock()
    mock_value = MagicMock()
    mock_news.find.return_value = _make_cursor([])
    mock_value.find.return_value = _make_cursor([])

    def get_col(name):
        return {"news_entities": mock_news, "value_entities": mock_value}.get(
            name, AsyncMock()
        )

    with patch("src.api.pools.mongodb") as mock_db:
        mock_db.get_collection.side_effect = get_col
        from src.api.pools import get_pools

        await get_pools("2026-03-22", market="US", include_stale=False)
        filter_arg = mock_news.find.call_args[0][0]
        assert filter_arg.get("status") == "active"


@pytest.mark.asyncio
async def test_pools_includes_stale_when_requested():
    mock_news = MagicMock()
    mock_value = MagicMock()
    mock_news.find.return_value = _make_cursor(
        [{"id": "old", "status": "stale", "score": 10}]
    )
    mock_value.find.return_value = _make_cursor([])

    def get_col(name):
        return {"news_entities": mock_news, "value_entities": mock_value}.get(
            name, AsyncMock()
        )

    with patch("src.api.pools.mongodb") as mock_db:
        mock_db.get_collection.side_effect = get_col
        from src.api.pools import get_pools

        result = await get_pools("2026-03-22", market="US", include_stale=True)
        assert len(result["news_entities"]) == 1


@pytest.mark.asyncio
async def test_pools_fallback_to_legacy():
    mock_news = MagicMock()
    mock_value = MagicMock()
    mock_legacy = AsyncMock()
    mock_news.find.return_value = _make_cursor([])
    mock_value.find.return_value = _make_cursor([])
    mock_legacy.find_one.side_effect = [
        {"type": "news", "items": [{"id": "legacy-n1"}]},
        {"type": "value", "items": [{"id": "legacy-v1"}]},
    ]

    def get_col(name):
        return {
            "news_entities": mock_news,
            "value_entities": mock_value,
            "pools": mock_legacy,
        }.get(name, AsyncMock())

    with patch("src.api.pools.mongodb") as mock_db:
        mock_db.get_collection.side_effect = get_col
        from src.api.pools import get_pools

        result = await get_pools("2026-03-22", market="US")
        assert result["news_entities"][0]["id"] == "legacy-n1"
