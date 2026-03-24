"""Tests for cache-first logic in get_live_pools().

Cache contract:
- Pool docs in MongoDB carry a ``cached_at`` ISO-8601 timestamp.
- If BOTH news and value docs exist and ``cached_at`` is < 2 hours old,
  return them immediately without calling any external API.
- If either doc is missing OR ``cached_at`` is >= 2 hours old, fetch live
  and overwrite with a fresh ``cached_at``.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now():
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _make_news_items():
    return [{"id": "n1", "title": "News 1", "direction": "bullish"}]


def _make_value_items():
    return [{"id": "v1", "ticker": "AAPL", "direction": "bullish"}]


def _mock_collection(find_one_side_effect):
    """Return an AsyncMock collection where find_one returns given side effects."""
    col = AsyncMock()
    col.find_one.side_effect = find_one_side_effect
    col.update_one = AsyncMock()
    return col


# ---------------------------------------------------------------------------
# Test 1 — Cache HIT: recent cached_at → skip external APIs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_pools_returns_cache_when_fresh():
    """When both docs exist with cached_at < 2 hours, skip external APIs."""
    fresh_ts = _iso(_utc_now() - timedelta(minutes=30))
    news_doc = {
        "type": "news",
        "date": "2026-03-23",
        "market": "US",
        "items": _make_news_items(),
        "cached_at": fresh_ts,
    }
    value_doc = {
        "type": "value",
        "date": "2026-03-23",
        "market": "US",
        "items": _make_value_items(),
        "cached_at": fresh_ts,
    }

    mock_col = _mock_collection([news_doc, value_doc])

    with patch("src.api.pools.mongodb") as mock_db, patch(
        "src.api.pools.fetch_real_news"
    ) as mock_news_api, patch("src.api.pools.fetch_real_stocks") as mock_stock_api:

        mock_db.get_collection.return_value = mock_col

        from src.api.pools import get_live_pools

        result = await get_live_pools("2026-03-23", market="US")

    # External APIs must NOT be called
    mock_news_api.assert_not_called()
    mock_stock_api.assert_not_called()

    assert result["news"] == _make_news_items()
    assert result["value"] == _make_value_items()


# ---------------------------------------------------------------------------
# Test 2 — Cache MISS: stale cached_at (> 2 hours) → fetch live
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_pools_fetches_live_when_stale():
    """When cached_at is > 2 hours old, external APIs are called."""
    stale_ts = _iso(_utc_now() - timedelta(hours=3))
    news_doc = {
        "type": "news",
        "date": "2026-03-23",
        "market": "US",
        "items": [{"id": "old_n"}],
        "cached_at": stale_ts,
    }
    value_doc = {
        "type": "value",
        "date": "2026-03-23",
        "market": "US",
        "items": [{"id": "old_v"}],
        "cached_at": stale_ts,
    }

    mock_col = _mock_collection([news_doc, value_doc])
    mock_col.update_one = AsyncMock()

    live_news = _make_news_items()
    live_value = _make_value_items()

    with patch("src.api.pools.mongodb") as mock_db, patch(
        "src.api.pools.fetch_real_news", new=AsyncMock(return_value=live_news)
    ), patch("src.api.pools.fetch_real_stocks", return_value=live_value), patch(
        "asyncio.to_thread", new=AsyncMock(return_value=live_value)
    ):

        mock_db.get_collection.return_value = mock_col

        from src.api.pools import get_live_pools

        result = await get_live_pools("2026-03-23", market="US")

    assert result["news"] == live_news
    assert result["value"] == live_value


# ---------------------------------------------------------------------------
# Test 3 — Cache MISS: no docs in MongoDB → fetch live
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_pools_fetches_live_when_no_cache():
    """When no cached docs exist, external APIs are called."""
    mock_col = _mock_collection([None, None])
    mock_col.update_one = AsyncMock()

    live_news = _make_news_items()
    live_value = _make_value_items()

    with patch("src.api.pools.mongodb") as mock_db, patch(
        "src.api.pools.fetch_real_news", new=AsyncMock(return_value=live_news)
    ), patch("src.api.pools.fetch_real_stocks", return_value=live_value), patch(
        "asyncio.to_thread", new=AsyncMock(return_value=live_value)
    ):

        mock_db.get_collection.return_value = mock_col

        from src.api.pools import get_live_pools

        result = await get_live_pools("2026-03-23", market="US")

    assert result["news"] == live_news
    assert result["value"] == live_value


# ---------------------------------------------------------------------------
# Test 4 — Cache write: fresh fetch writes cached_at to MongoDB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_pools_writes_cached_at_on_fetch():
    """After a live fetch, MongoDB update_one receives a cached_at field."""
    mock_col = _mock_collection([None, None])
    mock_col.update_one = AsyncMock()

    live_news = _make_news_items()
    live_value = _make_value_items()

    with patch("src.api.pools.mongodb") as mock_db, patch(
        "src.api.pools.fetch_real_news", new=AsyncMock(return_value=live_news)
    ), patch("src.api.pools.fetch_real_stocks", return_value=live_value), patch(
        "asyncio.to_thread", new=AsyncMock(return_value=live_value)
    ):

        mock_db.get_collection.return_value = mock_col

        from src.api.pools import get_live_pools

        await get_live_pools("2026-03-23", market="US")

    # Both update_one calls must include cached_at in $set
    assert mock_col.update_one.call_count == 2
    for c in mock_col.update_one.call_args_list:
        set_doc = c[0][1]["$set"]
        assert "cached_at" in set_doc, "cached_at must be written on live fetch"
