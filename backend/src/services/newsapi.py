"""NewsAPI integration — breaking headlines and article search.

Free tier: 100 req/day, 24h article delay, dev-only license.
"""

import hashlib
import os
from datetime import datetime, timezone

import httpx

from src.core.logger import get_logger
from src.database.mongodb import mongodb

log = get_logger("newsapi")

NEWSAPI_BASE_URL = "https://newsapi.org/v2"
NEWSAPI_KEY = os.environ.get("NEWSAPI_API_KEY", "")

# --- Keyword-based classification (lightweight, no ML) ---

_GEO_KEYWORDS = {
    "geopolitical",
    "nato",
    "sanctions",
    "trade war",
    "tariffs",
    "war",
    "opec",
    "g7",
    "g20",
    "imf",
    "world bank",
    "un ",
    "military",
    "invasion",
    "treaty",
    "summit",
    "diplomatic",
}
_MACRO_KEYWORDS = {
    "inflation",
    "interest rate",
    "gdp",
    "employment",
    "monetary policy",
    "fiscal policy",
    "treasury",
    "central bank",
    "federal reserve",
    "recession",
    "stimulus",
    "debt ceiling",
}
_SECTOR_MAP = {
    "energy": {"oil", "opec", "gas", "renewable", "solar", "wind", "energy"},
    "technology": {"ai", "chip", "semiconductor", "tech", "software", "cyber"},
    "finance": {"bank", "fed", "interest rate", "mortgage", "credit"},
    "healthcare": {"pharma", "drug", "vaccine", "health", "fda"},
    "commodities": {"gold", "rare earth", "copper", "lithium", "commodity"},
    "defense": {"military", "defense", "weapon", "nato", "army"},
    "trade": {"tariff", "trade", "import", "export", "sanctions"},
    "climate": {"climate", "carbon", "emission", "environmental"},
}


def _infer_scope_from_title(title: str) -> int:
    lower = title.lower()
    if any(k in lower for k in _GEO_KEYWORDS):
        return 5
    if any(k in lower for k in _MACRO_KEYWORDS):
        return 4
    matched_sectors = sum(
        1 for keywords in _SECTOR_MAP.values() if any(k in lower for k in keywords)
    )
    if matched_sectors >= 2:
        return 3
    return 2


def _infer_sectors_from_title(title: str) -> list[str]:
    lower = title.lower()
    return [
        sector
        for sector, keywords in _SECTOR_MAP.items()
        if any(k in lower for k in keywords)
    ]


def _newsapi_to_pool_item(article: dict, origin: str = "newsapi") -> dict:
    url = article.get("url", "")
    return {
        "id": f"na-{hashlib.sha256(url.encode()).hexdigest()[:10]}",
        "type": "news_event",
        "title": article.get("title", ""),
        "source": article.get("source", {}).get("name", "Unknown"),
        "url": url,
        "summary": (article.get("description", "") or "")[:200],
        "published_at": article.get("publishedAt", ""),
        "direction": "neutral",
        "confidence": 50,
        "sectors": _infer_sectors_from_title(article.get("title", "")),
        "scope": _infer_scope_from_title(article.get("title", "")),
        "origin": origin,
        "story_cluster_size": 1,
    }


# --- Rate limit tracking ---


async def _get_newsapi_call_count() -> int:
    col = mongodb.get_collection("newsapi_usage")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    doc = await col.find_one({"date": today})
    return doc.get("count", 0) if doc else 0


async def _increment_newsapi_call_count(source: str = "cron"):
    col = mongodb.get_collection("newsapi_usage")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await col.update_one(
        {"date": today},
        {"$inc": {"count": 1}, "$set": {"date": today, "last_source": source}},
        upsert=True,
    )


# --- Cache ---


async def _get_cached(cache_key: str) -> list[dict] | None:
    col = mongodb.get_collection("newsapi_cache")
    doc = await col.find_one({"key": cache_key}, {"_id": 0})
    if doc:
        log.info(
            "NewsAPI cache hit: %s (%d items)", cache_key, len(doc.get("articles", []))
        )
        return doc.get("articles", [])
    return None


async def _set_cache(cache_key: str, items: list[dict]):
    col = mongodb.get_collection("newsapi_cache")
    await col.update_one(
        {"key": cache_key},
        {
            "$set": {
                "key": cache_key,
                "articles": items,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )


# --- Public API ---


async def fetch_newsapi_headlines(
    category: str = "general",
    language: str = "en",
    page_size: int = 50,
    daily_limit: int = 100,
) -> list[dict]:
    """Fetch breaking headlines from /top-headlines."""
    if not NEWSAPI_KEY:
        log.warning("NEWSAPI_API_KEY not set")
        return []

    cache_key = f"newsapi:headlines:{category}:{language}:{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')}"
    cached = await _get_cached(cache_key)
    if cached is not None:
        return cached

    calls = await _get_newsapi_call_count()
    if calls >= daily_limit:
        log.warning("NewsAPI daily limit reached (%d/%d)", calls, daily_limit)
        return []

    try:
        log.info("NewsAPI headlines call #%d: category=%s", calls + 1, category)
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{NEWSAPI_BASE_URL}/top-headlines",
                params={
                    "apiKey": NEWSAPI_KEY,
                    "category": category,
                    "language": language,
                    "pageSize": page_size,
                },
            )
            data = r.json()

        await _increment_newsapi_call_count("cron")

        if data.get("status") != "ok":
            log.error("NewsAPI error: %s", data.get("message", "unknown"))
            return []

        articles = data.get("articles", [])
        items = [_newsapi_to_pool_item(a) for a in articles if a.get("url")]
        await _set_cache(cache_key, items)
        log.info("NewsAPI: fetched %d headlines", len(items))
        return items

    except Exception as e:
        log.error("NewsAPI headlines failed: %s", e)
        return []


async def fetch_newsapi_everything(
    query: str,
    sort_by: str = "relevancy",
    page_size: int = 10,
    daily_limit: int = 100,
) -> list[dict]:
    """Search articles via /everything. Used by agent fetch_news tool."""
    if not NEWSAPI_KEY:
        log.warning("NEWSAPI_API_KEY not set")
        return []

    cache_key = f"newsapi:everything:{query}:{sort_by}:{page_size}:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    cached = await _get_cached(cache_key)
    if cached is not None:
        return cached

    calls = await _get_newsapi_call_count()
    if calls >= daily_limit:
        log.warning("NewsAPI daily limit reached (%d/%d)", calls, daily_limit)
        return []

    try:
        log.info("NewsAPI everything call #%d: q=%s", calls + 1, query)
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{NEWSAPI_BASE_URL}/everything",
                params={
                    "apiKey": NEWSAPI_KEY,
                    "q": query,
                    "sortBy": sort_by,
                    "pageSize": page_size,
                    "language": "en",
                },
            )
            data = r.json()

        await _increment_newsapi_call_count("agent")

        if data.get("status") != "ok":
            log.error("NewsAPI error: %s", data.get("message", "unknown"))
            return []

        articles = data.get("articles", [])
        items = [
            _newsapi_to_pool_item(a, origin="agent_fetch")
            for a in articles
            if a.get("url")
        ]
        await _set_cache(cache_key, items)
        log.info("NewsAPI everything: %d results for '%s'", len(items), query)
        return items

    except Exception as e:
        log.error("NewsAPI everything failed: %s", e)
        return []
