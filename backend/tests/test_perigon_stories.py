from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.perigon import _story_to_pool_item, fetch_perigon_stories


def test_story_to_pool_item_basic():
    story = {
        "id": "abc123def456ghi789",
        "name": "China bans rare earth exports to US",
        "summary": "Beijing announced...",
        "uniqueCount": 42,
        "totalCount": 60,
        "initializedAt": "2026-03-24T08:00:00Z",
        "updatedAt": "2026-03-24T09:00:00Z",
        "topics": [{"name": "Sanctions"}],
        "categories": [{"name": "Geopolitical"}],
        "sentiment": {"positive": 0.1, "negative": 0.8},
    }
    item = _story_to_pool_item(story)
    assert item["id"].startswith("pg-story-")
    assert item["id"] == "pg-story-abc123def4"
    assert item["title"] == "China bans rare earth exports to US"
    assert item["story_cluster_size"] == 42
    assert item["origin"] == "perigon"
    assert item["published_at"] == "2026-03-24T08:00:00Z"
    assert item["scope"] >= 4


def test_story_cluster_size_preserved():
    story = {
        "id": "xyz789",
        "name": "Local city council vote",
        "summary": "...",
        "uniqueCount": 3,
        "totalCount": 5,
        "initializedAt": "2026-03-24T08:00:00Z",
        "updatedAt": "2026-03-24T09:00:00Z",
        "topics": [],
        "categories": [],
        "sentiment": {},
    }
    item = _story_to_pool_item(story)
    assert item["story_cluster_size"] == 3


def test_story_fallback_to_total_count():
    """When uniqueCount is missing, fall back to totalCount."""
    story = {
        "id": "fallback123",
        "name": "Test story",
        "summary": "...",
        "totalCount": 15,
        "initializedAt": "2026-03-24T08:00:00Z",
        "updatedAt": "2026-03-24T09:00:00Z",
        "topics": [],
        "categories": [],
        "sentiment": {},
    }
    item = _story_to_pool_item(story)
    assert item["story_cluster_size"] == 15


def test_story_fallback_to_updated_at():
    """When initializedAt is missing, fall back to updatedAt."""
    story = {
        "id": "noinit123",
        "name": "Test story",
        "summary": "...",
        "uniqueCount": 5,
        "updatedAt": "2026-03-24T10:00:00Z",
        "topics": [],
        "categories": [],
        "sentiment": {},
    }
    item = _story_to_pool_item(story)
    assert item["published_at"] == "2026-03-24T10:00:00Z"


# --- fetch_perigon_stories() tests ---


@pytest.mark.asyncio
@patch("src.services.perigon.PERIGON_API_KEY", "test-key")
@patch("src.services.perigon._get_cached", new_callable=AsyncMock, return_value=None)
@patch("src.services.perigon._get_call_count_today", new_callable=AsyncMock, return_value=0)
@patch("src.services.perigon._increment_call_count", new_callable=AsyncMock)
@patch("src.services.perigon._set_cache", new_callable=AsyncMock)
async def test_fetch_perigon_stories_uses_stories_all_path(
    mock_set_cache, mock_inc, mock_count, mock_cached
):
    """Verify fetch_perigon_stories hits /v1/stories/all and parses 'results' key."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": 200,
        "results": [
            {
                "id": "story1",
                "name": "Fed holds rates steady",
                "summary": "The Federal Reserve...",
                "uniqueCount": 25,
                "totalCount": 30,
                "initializedAt": "2026-03-25T12:00:00Z",
                "updatedAt": "2026-03-25T13:00:00Z",
                "topics": [{"name": "Federal Reserve"}],
                "categories": [{"name": "Economy"}],
                "sentiment": {"positive": 0.3, "negative": 0.2},
            },
        ],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.services.perigon.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_perigon_stories(size=5)

    # Verify the correct URL path was called
    call_args = mock_client.get.call_args
    url = call_args[0][0]
    assert "/stories/all" in url, f"Expected /stories/all in URL, got: {url}"

    # Verify results were parsed correctly
    assert len(result) == 1
    assert result[0]["title"] == "Fed holds rates steady"
    assert result[0]["story_cluster_size"] == 25
    assert result[0]["origin"] == "perigon"


@pytest.mark.asyncio
@patch("src.services.perigon.PERIGON_API_KEY", "test-key")
@patch("src.services.perigon._get_cached", new_callable=AsyncMock, return_value=None)
@patch("src.services.perigon._get_call_count_today", new_callable=AsyncMock, return_value=0)
@patch("src.services.perigon._increment_call_count", new_callable=AsyncMock)
async def test_fetch_perigon_stories_non_200_returns_empty(
    mock_inc, mock_count, mock_cached
):
    """Verify non-200 status from Perigon returns empty list."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": 400,
        "message": "Invalid API key",
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.services.perigon.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_perigon_stories()

    assert result == []
