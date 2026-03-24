from src.services.perigon import _story_to_pool_item


def test_story_to_pool_item_basic():
    story = {
        "storyId": "abc123",
        "title": "China bans rare earth exports to US",
        "summary": "Beijing announced...",
        "numArticles": 42,
        "initialPublishedAt": "2026-03-24T08:00:00Z",
        "topics": [{"name": "Trade"}],
        "categories": [{"name": "World"}],
        "sentiment": {"positive": 0.1, "negative": 0.8},
    }
    item = _story_to_pool_item(story)
    assert item["id"].startswith("pg-story-")
    assert item["story_cluster_size"] == 42
    assert item["origin"] == "perigon"
    assert item["scope"] >= 4


def test_story_cluster_size_preserved():
    story = {
        "storyId": "xyz",
        "title": "Local city council vote",
        "summary": "...",
        "numArticles": 3,
        "initialPublishedAt": "2026-03-24T08:00:00Z",
        "topics": [],
        "categories": [],
        "sentiment": {},
    }
    item = _story_to_pool_item(story)
    assert item["story_cluster_size"] == 3
