import asyncio
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter
from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.services.data_sources import fetch_real_news, fetch_real_stocks

log = get_logger("api.pools")
router = APIRouter(prefix="/api/pools", tags=["pools"])


@router.get("/{date}")
async def get_pools(date: str, market: str = "US", include_stale: bool = False):
    """Get news and value pool entities.

    Entity-based path returns all active entities for the market (entities are
    living records, not date-stamped snapshots). The ``date`` param is only used
    for the legacy fallback during migration."""
    news_col = mongodb.get_collection("news_entities")
    value_col = mongodb.get_collection("value_entities")

    query: dict = {"market": market}
    if not include_stale:
        query["status"] = "active"

    news_entities = await news_col.find(query, {"_id": 0}).to_list(length=500)
    value_entities = await value_col.find(query, {"_id": 0}).to_list(length=500)

    # Legacy fallback during migration
    if not news_entities and not value_entities:
        legacy_col = mongodb.get_collection("pools")
        legacy_news = await legacy_col.find_one(
            {"type": "news", "date": date, "market": market}, {"_id": 0}
        )
        legacy_value = await legacy_col.find_one(
            {"type": "value", "date": date, "market": market}, {"_id": 0}
        )
        raw_news = (legacy_news or {}).get("items", [])
        raw_value = (legacy_value or {}).get("items", [])
        news_entities = raw_news if isinstance(raw_news, list) else []
        value_entities = raw_value if isinstance(raw_value, list) else []

    log.info(
        "GET /pools/%s market=%s stale=%s — %d news, %d values",
        date,
        market,
        include_stale,
        len(news_entities),
        len(value_entities),
    )
    return {"news_entities": news_entities, "value_entities": value_entities}


_CACHE_TTL = timedelta(hours=2)


def _is_fresh(cached_at_iso: str | None) -> bool:
    """Return True if cached_at is within the 2-hour TTL."""
    if not cached_at_iso:
        return False
    try:
        cached_at = datetime.fromisoformat(cached_at_iso)
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - cached_at) < _CACHE_TTL
    except ValueError:
        return False


@router.get("/live/{date}")
async def get_live_pools(date: str, market: str = "US", topics: str = ""):
    """Fetch live pools from real APIs (Alpha Vantage + Yahoo Finance).

    Cache-first: if MongoDB has both news and value docs with a ``cached_at``
    timestamp < 2 hours old, return them immediately without hitting external
    APIs.  Otherwise fetch live, write results (with fresh ``cached_at``), and
    return.
    """
    collection = mongodb.get_collection("pools")

    # --- Cache-first read ---
    news_doc, value_doc = await asyncio.gather(
        collection.find_one(
            {"type": "news", "date": date, "market": market}, {"_id": 0}
        ),
        collection.find_one(
            {"type": "value", "date": date, "market": market}, {"_id": 0}
        ),
    )

    if (
        news_doc
        and value_doc
        and _is_fresh(news_doc.get("cached_at"))
        and _is_fresh(value_doc.get("cached_at"))
    ):
        log.info(
            "GET /pools/live/%s — cache HIT (%d news, %d values)",
            date,
            len(news_doc.get("items", [])),
            len(value_doc.get("items", [])),
        )
        return {"news": news_doc.get("items", []), "value": value_doc.get("items", [])}

    # --- Cache miss: fetch live in parallel (return_exceptions to preserve fallback) ---
    log.info("GET /pools/live/%s — cache MISS, fetching live", date)
    news_result, value_result = await asyncio.gather(
        fetch_real_news(limit=10, topics=topics),
        asyncio.to_thread(fetch_real_stocks),
        return_exceptions=True,
    )

    news = news_result if isinstance(news_result, list) else []
    value = value_result if isinstance(value_result, list) else []

    if isinstance(news_result, Exception):
        log.warning("Live news fetch failed: %s", news_result)
    if isinstance(value_result, Exception):
        log.warning("Live stock fetch failed: %s", value_result)

    # Track whether live fetch succeeded (for cached_at decision)
    news_fetched_live = isinstance(news_result, list) and bool(news_result)
    value_fetched_live = isinstance(value_result, list) and bool(value_result)

    if not news:
        log.info("Live news fetch empty, falling back to cached")
        news = (news_doc or {}).get("items", [])

    if not value:
        log.info("Live stock fetch empty, falling back to cached")
        value = (value_doc or {}).get("items", [])

    # --- Write back with cached_at only if live fetch succeeded (Fix #5) ---
    now_iso = datetime.now(timezone.utc).isoformat()
    writes = []
    if news_fetched_live and news:
        writes.append(
            collection.update_one(
                {"type": "news", "date": date, "market": market},
                {
                    "$set": {
                        "type": "news",
                        "date": date,
                        "market": market,
                        "items": news,
                        "cached_at": now_iso,
                    }
                },
                upsert=True,
            )
        )
    if value_fetched_live and value:
        writes.append(
            collection.update_one(
                {"type": "value", "date": date, "market": market},
                {
                    "$set": {
                        "type": "value",
                        "date": date,
                        "market": market,
                        "items": value,
                        "cached_at": now_iso,
                    }
                },
                upsert=True,
            )
        )
    if writes:
        await asyncio.gather(*writes)

    log.info(
        "GET /pools/live/%s — %d news, %d values (topics=%s, cached)",
        date,
        len(news),
        len(value),
        topics or "all",
    )
    return {"news": news, "value": value}
