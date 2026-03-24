from src.services.perigon import _story_to_pool_item


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
