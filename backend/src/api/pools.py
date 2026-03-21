from fastapi import APIRouter

from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.services.data_sources import fetch_real_news, fetch_real_stocks

log = get_logger("api.pools")

router = APIRouter(prefix="/api/pools", tags=["pools"])


@router.get("/{date}")
async def get_pools(date: str, market: str = "US"):
    """Get news and value pools for a given date."""
    collection = mongodb.get_collection("pools")
    news = await collection.find_one(
        {"type": "news", "date": date, "market": market}, {"_id": 0}
    )
    value = await collection.find_one(
        {"type": "value", "date": date, "market": market}, {"_id": 0}
    )
    news_items = (news or {}).get("items", [])
    value_items = (value or {}).get("items", [])
    log.info(
        "GET /pools/%s market=%s — %d news, %d values",
        date,
        market,
        len(news_items),
        len(value_items),
    )
    return {"news": news_items, "value": value_items}


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

    log.info(
        "GET /pools/live/%s — %d news, %d values (topics=%s)",
        date,
        len(news),
        len(value),
        topics or "all",
    )
    return {"news": news, "value": value}
