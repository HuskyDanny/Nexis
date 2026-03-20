from fastapi import APIRouter

from src.core.logger import get_logger
from src.database.mongodb import mongodb

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
