### Task 7b: Pools Entity Endpoint

**Parent:** [Session & Pool Pipeline Plan](../2026-03-22-session-pool-entity-pipeline.md)
**See also:** [[task-7a-lifespan-and-cas]]

**Files:**
- Modify: `backend/src/api/pools.py` (entity-based response + stale filtering + legacy fallback)
- Create: `backend/tests/api/test_pools_entities.py`
- Depends on: Task 2 (entity collections), Task 7a (lifespan)

---

- [ ] **Step 1: RED — Entity pools endpoint tests**

Create `backend/tests/api/test_pools_entities.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

def _make_cursor(items):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=items)
    return cursor

@pytest.mark.asyncio
async def test_pools_returns_entity_format():
    mock_news = MagicMock()
    mock_value = MagicMock()
    mock_news.find.return_value = _make_cursor([
        {"id": "abc", "canonical_title": "Test", "score": 80, "status": "active"}])
    mock_value.find.return_value = _make_cursor([
        {"id": "AAPL:US", "ticker": "AAPL", "score": 65, "status": "active"}])

    def get_col(name):
        return {"news_entities": mock_news, "value_entities": mock_value}.get(name, AsyncMock())

    with patch("src.api.pools.mongodb") as mock_db:
        mock_db.get_collection.side_effect = get_col
        from src.api.pools import get_pools
        result = await get_pools("2026-03-22", market="US")
        assert "news_entities" in result
        assert "value_entities" in result
        assert result["news_entities"][0]["id"] == "abc"

@pytest.mark.asyncio
async def test_pools_filters_stale_by_default():
    mock_news = MagicMock()
    mock_value = MagicMock()
    mock_news.find.return_value = _make_cursor([])
    mock_value.find.return_value = _make_cursor([])

    def get_col(name):
        return {"news_entities": mock_news, "value_entities": mock_value}.get(name, AsyncMock())

    with patch("src.api.pools.mongodb") as mock_db:
        mock_db.get_collection.side_effect = get_col
        from src.api.pools import get_pools
        await get_pools("2026-03-22", market="US", include_stale=False)
        filter_arg = mock_news.find.call_args[0][0]
        assert filter_arg.get("status") == "active"

@pytest.mark.asyncio
async def test_pools_includes_stale_when_requested():
    mock_news = MagicMock()
    mock_value = MagicMock()
    mock_news.find.return_value = _make_cursor([{"id": "old", "status": "stale", "score": 10}])
    mock_value.find.return_value = _make_cursor([])

    def get_col(name):
        return {"news_entities": mock_news, "value_entities": mock_value}.get(name, AsyncMock())

    with patch("src.api.pools.mongodb") as mock_db:
        mock_db.get_collection.side_effect = get_col
        from src.api.pools import get_pools
        result = await get_pools("2026-03-22", market="US", include_stale=True)
        assert len(result["news_entities"]) == 1

@pytest.mark.asyncio
async def test_pools_fallback_to_legacy():
    mock_news = MagicMock()
    mock_value = MagicMock()
    mock_legacy = AsyncMock()
    mock_news.find.return_value = _make_cursor([])
    mock_value.find.return_value = _make_cursor([])
    mock_legacy.find_one.side_effect = [
        {"type": "news", "items": [{"id": "legacy-n1"}]},
        {"type": "value", "items": [{"id": "legacy-v1"}]},
    ]

    def get_col(name):
        return {"news_entities": mock_news, "value_entities": mock_value,
                "pools": mock_legacy}.get(name, AsyncMock())

    with patch("src.api.pools.mongodb") as mock_db:
        mock_db.get_collection.side_effect = get_col
        from src.api.pools import get_pools
        result = await get_pools("2026-03-22", market="US")
        assert result["news_entities"][0]["id"] == "legacy-n1"
```

Run: `cd backend && python -m pytest tests/api/test_pools_entities.py -v` — 4 FAIL

- [ ] **Step 2: GREEN — Replace pools.py with entity-based endpoint**

Replace `backend/src/api/pools.py`:

```python
from fastapi import APIRouter
from src.core.logger import get_logger
from src.database.mongodb import mongodb

log = get_logger("api.pools")
router = APIRouter(prefix="/api/pools", tags=["pools"])

@router.get("/{date}")
async def get_pools(date: str, market: str = "US", include_stale: bool = False):
    """Get news and value entities for a given date.
    Queries entity collections first; falls back to legacy pools if empty."""
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
            {"type": "news", "date": date, "market": market}, {"_id": 0})
        legacy_value = await legacy_col.find_one(
            {"type": "value", "date": date, "market": market}, {"_id": 0})
        news_entities = (legacy_news or {}).get("items", [])
        value_entities = (legacy_value or {}).get("items", [])

    log.info("GET /pools/%s market=%s stale=%s — %d news, %d values",
             date, market, include_stale, len(news_entities), len(value_entities))
    return {"news_entities": news_entities, "value_entities": value_entities}
```

Run: `cd backend && python -m pytest tests/api/test_pools_entities.py -v` — 4 PASS

- [ ] **Step 3: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

Expected: all tests PASS, no regressions
