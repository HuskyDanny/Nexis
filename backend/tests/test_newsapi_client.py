from src.services.newsapi import (
    _newsapi_to_pool_item,
    _infer_scope_from_title,
    _infer_sectors_from_title,
)


def test_newsapi_to_pool_item_basic():
    article = {
        "title": "EU imposes new carbon tariffs on steel imports",
        "source": {"name": "Reuters"},
        "url": "https://reuters.com/article/123",
        "description": "The European Union announced...",
        "publishedAt": "2026-03-24T10:00:00Z",
    }
    item = _newsapi_to_pool_item(article)
    assert item["id"].startswith("na-")
    assert item["origin"] == "newsapi"
    assert item["title"] == article["title"]
    assert item["source"] == "Reuters"
    assert item["story_cluster_size"] == 1


def test_newsapi_to_pool_item_truncates_summary():
    article = {
        "title": "Test",
        "source": {"name": "AP"},
        "url": "https://example.com",
        "description": "x" * 300,
        "publishedAt": "2026-03-24T10:00:00Z",
    }
    item = _newsapi_to_pool_item(article)
    assert len(item["summary"]) <= 200


def test_infer_scope_geopolitical():
    assert _infer_scope_from_title("NATO deploys troops to Baltic states") >= 4


def test_infer_scope_company():
    assert _infer_scope_from_title("Apple releases new iPhone model") <= 2


def test_infer_sectors_from_title():
    sectors = _infer_sectors_from_title("OPEC cuts oil production amid energy crisis")
    assert any("energy" in s.lower() for s in sectors)
