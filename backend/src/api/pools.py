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


@router.get("/live/{date}")
async def get_live_pools(date: str, market: str = "US", topics: str = ""):
    """Fetch live pools from real APIs (Alpha Vantage + Yahoo Finance).
    Falls back to MongoDB mock data if APIs fail."""
    import asyncio

    news = await fetch_real_news(limit=10, topics=topics)
    value = await asyncio.to_thread(fetch_real_stocks)

    if not news:
        log.info("Live news fetch empty, falling back to mock")
        collection = mongodb.get_collection("pools")
        mock = await collection.find_one(
            {"type": "news", "date": date, "market": market}, {"_id": 0}
        )
        news = (mock or {}).get("items", [])

    if not value:
        log.info("Live stock fetch empty, falling back to mock")
        collection = mongodb.get_collection("pools")
        mock = await collection.find_one(
            {"type": "value", "date": date, "market": market}, {"_id": 0}
        )
        value = (mock or {}).get("items", [])

    # Cache live data in MongoDB so thinking sessions can find it by date
    if news or value:
        collection = mongodb.get_collection("pools")
        if news:
            await collection.update_one(
                {"type": "news", "date": date, "market": market},
                {
                    "$set": {
                        "type": "news",
                        "date": date,
                        "market": market,
                        "items": news,
                    }
                },
                upsert=True,
            )
        if value:
            await collection.update_one(
                {"type": "value", "date": date, "market": market},
                {
                    "$set": {
                        "type": "value",
                        "date": date,
                        "market": market,
                        "items": value,
                    }
                },
                upsert=True,
            )

    log.info(
        "GET /pools/live/%s — %d news, %d values (topics=%s, cached)",
        date,
        len(news),
        len(value),
        topics or "all",
    )
    return {"news": news, "value": value}
