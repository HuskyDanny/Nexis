"""Perigon news API integration — AI-native news with pre-classified metadata.

RATE LIMIT: 150 calls/month. Every call is cached in MongoDB.
Max 10 calls per session. Check cache first, always.
"""

import os
from datetime import datetime, timezone

import httpx

from src.core.logger import get_logger
from src.database.mongodb import mongodb

log = get_logger("perigon")

PERIGON_API_KEY = os.environ.get("PERIGON_API_KEY", "")
PERIGON_BASE_URL = "https://api.goperigon.com/v1"


async def _get_call_count_today() -> int:
    """Track daily API calls to stay within limits."""
    col = mongodb.get_collection("perigon_usage")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    doc = await col.find_one({"date": today})
    return doc.get("count", 0) if doc else 0


async def _increment_call_count():
    col = mongodb.get_collection("perigon_usage")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await col.update_one(
        {"date": today},
        {"$inc": {"count": 1}, "$set": {"date": today}},
        upsert=True,
    )


async def _get_cached(cache_key: str) -> list[dict] | None:
    """Check MongoDB cache for previous results."""
    col = mongodb.get_collection("perigon_cache")
    doc = await col.find_one({"key": cache_key}, {"_id": 0})
    if doc:
        log.info(
            "Perigon cache hit for key=%s (%d articles)",
            cache_key,
            len(doc.get("articles", [])),
        )
        return doc.get("articles", [])
    return None


async def _set_cache(cache_key: str, articles: list[dict]):
    """Cache results in MongoDB."""
    col = mongodb.get_collection("perigon_cache")
    await col.update_one(
        {"key": cache_key},
        {
            "$set": {
                "key": cache_key,
                "articles": articles,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )


def _classify_scope(article: dict) -> int:
    """Derive scope score (1-5) from Perigon's pre-classified metadata."""
    topics = [t.get("name", "").lower() for t in article.get("topics", [])]
    categories = [c.get("name", "").lower() for c in article.get("categories", [])]
    labels = [l.get("name", "").lower() for l in article.get("labels", [])]
    companies = article.get("companies", [])
    locations = article.get("locations", [])

    # Low content = noise
    if "low content" in labels or "opinion" in labels:
        return 1

    # Company-specific (SEC filings, earnings, single company)
    if len(companies) == 1 and not any(
        t in topics
        for t in ["markets", "economy", "federal reserve", "trade", "geopolitical"]
    ):
        return 1

    # Global/geopolitical
    geo_keywords = {
        "geopolitical",
        "federal reserve",
        "trade war",
        "trade",
        "sanctions",
        "war",
        "opec",
        "g7",
        "g20",
        "nato",
        "imf",
        "world bank",
        "world",
    }
    if any(k in " ".join(topics + categories).lower() for k in geo_keywords):
        return 5

    # National/macro
    macro_keywords = {
        "economy",
        "inflation",
        "interest rates",
        "gdp",
        "employment",
        "monetary policy",
        "fiscal policy",
        "treasury",
    }
    if any(k in " ".join(topics + categories).lower() for k in macro_keywords):
        return 4

    # Industry/trend
    industry_keywords = {
        "technology",
        "energy",
        "healthcare",
        "finance",
        "real estate",
        "markets",
    }
    if any(k in " ".join(topics + categories).lower() for k in industry_keywords):
        return 3

    # Sector
    if len(companies) > 1:
        return 2

    return 2  # Default: sector-level


def _classify_impact(article: dict) -> int:
    """Derive impact score (1-5) from sentiment strength and content."""
    sentiment = article.get("sentiment", {})
    pos = sentiment.get("positive", 0)
    neg = sentiment.get("negative", 0)

    # Strong sentiment = high impact
    strength = max(pos, neg)
    if strength > 0.8:
        return 5
    if strength > 0.6:
        return 4
    if strength > 0.4:
        return 3
    if strength > 0.2:
        return 2
    return 1


def _to_pool_item(article: dict) -> dict:
    """Convert Perigon article to our pool item format."""
    sentiment = article.get("sentiment", {})
    pos = sentiment.get("positive", 0)
    neg = sentiment.get("negative", 0)

    if pos > neg + 0.15:
        direction = "bullish"
    elif neg > pos + 0.15:
        direction = "bearish"
    else:
        direction = "neutral"

    scope = _classify_scope(article)
    impact = _classify_impact(article)

    topics = [t.get("name", "") for t in article.get("topics", [])]
    categories = [c.get("name", "") for c in article.get("categories", [])]

    return {
        "id": f"pg-{article.get('articleId', '')[:10]}",
        "type": "news_event",
        "title": article.get("title", ""),
        "source": article.get("source", {}).get("name", "Unknown"),
        "url": article.get("url", ""),
        "summary": article.get("summary", article.get("description", ""))[:200],
        "published_at": article.get("pubDate", ""),
        "direction": direction,
        "confidence": round(max(pos, neg) * 100),
        "sectors": (topics + categories)[:5],
        "sentiment_score": round(pos - neg, 3),
        "scope": scope,
        "impact": impact,
        "scope_impact": scope * impact,  # Combined score for ranking
        "metadata": {
            "sentiment": sentiment,
            "topics": topics,
            "categories": categories,
            "companies": [c.get("name", "") for c in article.get("companies", [])],
            "locations": [l.get("name", "") for l in article.get("locations", [])],
            "event_types": [e.get("name", "") for e in article.get("eventTypes", [])],
            "labels": [l.get("name", "") for l in article.get("labels", [])],
        },
    }


async def fetch_perigon_news(
    query: str = "economy markets geopolitical trade climate policy",
    size: int = 10,
    source_group: str = "top100",
) -> list[dict]:
    """Fetch news from Perigon with caching. Returns pool items sorted by scope*impact."""
    if not PERIGON_API_KEY:
        log.warning("PERIGON_API_KEY not set")
        return []

    # Check cache first
    cache_key = f"perigon:{query}:{size}:{source_group}:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    cached = await _get_cached(cache_key)
    if cached is not None:
        return cached

    # Check rate limit
    calls_today = await _get_call_count_today()
    if calls_today >= 10:
        log.warning("Perigon daily call limit reached (%d/10)", calls_today)
        return []

    try:
        log.info("Perigon API call #%d: q=%s size=%d", calls_today + 1, query, size)
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{PERIGON_BASE_URL}/all",
                params={
                    "apiKey": PERIGON_API_KEY,
                    "q": query,
                    "size": size,
                    "sortBy": "relevance",
                    "sourceGroup": source_group,
                },
            )
            data = r.json()

        await _increment_call_count()

        if data.get("status") != 200:
            log.error("Perigon error: %s", data.get("message", "unknown"))
            return []

        articles = data.get("articles", [])
        pool_items = [_to_pool_item(a) for a in articles]

        # Sort by scope * impact descending (macro first)
        pool_items.sort(key=lambda x: x.get("scope_impact", 0), reverse=True)

        # Cache the results
        await _set_cache(cache_key, pool_items)
        log.info(
            "Perigon: fetched %d articles, cached as %s", len(pool_items), cache_key
        )

        return pool_items

    except Exception as e:
        log.error("Perigon fetch failed: %s", e)
        return []


def _story_to_pool_item(story: dict) -> dict:
    """Convert Perigon /stories response to pool item format."""
    sentiment = story.get("sentiment", {})
    pos = sentiment.get("positive", 0)
    neg = sentiment.get("negative", 0)

    if pos > neg + 0.15:
        direction = "bullish"
    elif neg > pos + 0.15:
        direction = "bearish"
    else:
        direction = "neutral"

    scope = _classify_scope(story)
    impact = _classify_impact(story)

    topics = [t.get("name", "") for t in story.get("topics", [])]
    categories = [c.get("name", "") for c in story.get("categories", [])]
    num_articles = story.get("numArticles", story.get("articles_count", 0))

    return {
        "id": f"pg-story-{story.get('storyId', '')[:10]}",
        "type": "news_event",
        "origin": "perigon",
        "title": story.get("title", ""),
        "source": "perigon-stories",
        "url": story.get("url", ""),
        "summary": story.get("summary", "")[:200],
        "published_at": story.get("initialPublishedAt", story.get("updatedAt", "")),
        "direction": direction,
        "confidence": round(max(pos, neg) * 100),
        "sectors": (topics + categories)[:5],
        "sentiment_score": round(pos - neg, 3),
        "scope": scope,
        "impact": impact,
        "scope_impact": scope * impact,
        "story_cluster_size": num_articles,
        "metadata": {
            "sentiment": sentiment,
            "topics": topics,
            "categories": categories,
        },
    }


async def fetch_perigon_stories(
    categories: list[str] | None = None,
    size: int = 10,
    source_group: str = "top100",
) -> list[dict]:
    """Fetch clustered stories from Perigon /v1/stories endpoint.

    Stories represent clusters of articles about the same event.
    High numArticles = broad coverage = likely high-impact macro event.
    Returns pool items sorted by cluster size descending.
    """
    if not PERIGON_API_KEY:
        log.warning("PERIGON_API_KEY not set")
        return []

    if categories is None:
        categories = ["Politics", "World", "Environment", "Business", "Science"]

    exclude_categories = ["Opinion", "Non-news", "Paid News"]

    cache_key = (
        f"perigon-stories:{','.join(sorted(categories))}:{size}:{source_group}"
        f":{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    )
    cached = await _get_cached(cache_key)
    if cached is not None:
        return cached

    calls_today = await _get_call_count_today()
    if calls_today >= 10:
        log.warning("Perigon daily call limit reached (%d/10)", calls_today)
        return []

    try:
        log.info(
            "Perigon stories API call #%d: categories=%s size=%d",
            calls_today + 1,
            categories,
            size,
        )
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{PERIGON_BASE_URL}/stories",
                params={
                    "apiKey": PERIGON_API_KEY,
                    "size": size,
                    "category": categories,
                    "notCategory": exclude_categories,
                    "sourceGroup": source_group,
                    "sortBy": "updatedAt",
                },
            )
            data = r.json()

        await _increment_call_count()

        if data.get("status") != 200:
            log.error("Perigon stories error: %s", data.get("message", "unknown"))
            return []

        stories = data.get("results", data.get("stories", []))
        pool_items = [_story_to_pool_item(s) for s in stories]

        # Sort by cluster size descending — bigger clusters = more macro signal
        pool_items.sort(key=lambda x: x.get("story_cluster_size", 0), reverse=True)

        await _set_cache(cache_key, pool_items)
        log.info(
            "Perigon stories: fetched %d stories, cached as %s",
            len(pool_items),
            cache_key,
        )

        return pool_items

    except Exception as e:
        log.error("Perigon stories fetch failed: %s", e)
        return []
