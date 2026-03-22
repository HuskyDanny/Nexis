### Task 7a: Redis Lifespan + CAS Guard

**Parent:** [Session & Pool Pipeline Plan](../2026-03-22-session-pool-entity-pipeline.md)
**See also:** [[task-7b-pools-entity-endpoint]]

**Files:**
- Modify: `backend/src/main.py` (add Redis to lifespan)
- Modify: `backend/src/api/thinking.py` (CAS guard on /step)
- Create: `backend/tests/api/test_lifespan.py`, `backend/tests/api/test_thinking_cas.py`
- Depends on: Task 1 (Redis client)

---

- [ ] **Step 1: RED — Redis lifespan test**

Create `backend/tests/api/test_lifespan.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_lifespan_connects_redis():
    with patch("src.main.mongodb") as mock_mongo, \
         patch("src.main.redis_client") as mock_redis:
        mock_mongo.connect = AsyncMock()
        mock_mongo.close = AsyncMock()
        mock_redis.connect = AsyncMock()
        mock_redis.close = AsyncMock()
        from src.main import lifespan, app
        async with lifespan(app):
            mock_mongo.connect.assert_called_once()
            mock_redis.connect.assert_called_once()
        mock_mongo.close.assert_called_once()
        mock_redis.close.assert_called_once()
```

Run: `cd backend && python -m pytest tests/api/test_lifespan.py -v` — FAIL (no `redis_client` in main.py)

- [ ] **Step 2: GREEN — Update main.py lifespan**

Replace `backend/src/main.py`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.core.logger import get_logger

log = get_logger("app")

@asynccontextmanager
async def lifespan(_: FastAPI):
    from src.database.mongodb import mongodb
    from src.database.redis import redis_client

    log.info("Starting up — connecting to MongoDB")
    await mongodb.connect(settings.mongodb_url)
    log.info("MongoDB connected")
    log.info("Connecting to Redis")
    try:
        await redis_client.connect(settings.redis_url)
        log.info("Redis connected")
    except Exception as e:
        log.warning("Redis connection failed (non-fatal): %s", e)
    yield
    log.info("Shutting down")
    await redis_client.close()
    await mongodb.close()

app = FastAPI(title="Financial Agent v2", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.api.graphs import router as graphs_router
from src.api.nodes import router as nodes_router
from src.api.pools import router as pools_router
from src.api.thinking import router as thinking_router

app.include_router(graphs_router)
app.include_router(nodes_router)
app.include_router(pools_router)
app.include_router(thinking_router)

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
```

Run: `cd backend && python -m pytest tests/api/test_lifespan.py -v` — PASS

- [ ] **Step 3: RED — CAS guard tests**

Create `backend/tests/api/test_thinking_cas.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_step_uses_find_one_and_update_cas():
    mock_col = AsyncMock()
    mock_col.find_one_and_update.return_value = {
        "id": "abc123", "status": "thinking", "version": 2,
        "current_layer": 0, "max_depth": 3,
        "nodes": [], "edges": [], "news_pool": [], "value_pool": [],
    }
    with patch("src.api.thinking.mongodb") as mock_db:
        mock_db.get_collection.return_value = mock_col
        from src.api.thinking import think_step
        await think_step("abc123")
        mock_col.find_one_and_update.assert_called_once()
        call_args = mock_col.find_one_and_update.call_args
        filter_arg = call_args[0][0] if call_args[0] else call_args[1].get("filter", {})
        assert "status" in filter_arg

@pytest.mark.asyncio
async def test_step_returns_409_on_cas_failure():
    mock_col = AsyncMock()
    mock_col.find_one_and_update.return_value = None
    with patch("src.api.thinking.mongodb") as mock_db:
        mock_db.get_collection.return_value = mock_col
        from fastapi import HTTPException
        from src.api.thinking import think_step
        with pytest.raises(HTTPException) as exc_info:
            await think_step("abc123")
        assert exc_info.value.status_code == 409
```

Run: `cd backend && python -m pytest tests/api/test_thinking_cas.py -v` — FAIL (uses find_one not find_one_and_update)

- [ ] **Step 4: GREEN — Replace think_step with CAS guard**

In `backend/src/api/thinking.py`, replace the `think_step` function. Key change at the top — swap the `find_one` + status check + `update_one` with an atomic `find_one_and_update`:

```python
@router.post("/{session_id}/step", response_model=StepResponse)
async def think_step(session_id: str):
    """Execute one layer of thinking. Uses CAS to prevent concurrent steps."""
    from pymongo import ReturnDocument

    col = mongodb.get_collection("thinking_sessions")

    # CAS: atomically claim the session for thinking
    session = await col.find_one_and_update(
        {"id": session_id, "status": {"$in": ["paused", "idle"]}},
        {"$set": {"status": "thinking"}, "$inc": {"version": 1}},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    if not session:
        existing = await col.find_one({"id": session_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(
            status_code=409,
            detail=f"Cannot step: session is {existing['status']} (concurrent modification)",
        )

    current_layer = session["current_layer"]
    next_layer = current_layer + 1
    if next_layer > session["max_depth"]:
        await col.update_one({"id": session_id}, {"$set": {"status": "paused"}})
        raise HTTPException(status_code=400, detail="Max depth reached. Use /match.")

    log.info("Session %s: stepping to layer %d", session_id, next_layer)
    # ... rest of function body unchanged (mock reasoning, persist nodes/edges) ...
```

The mock reasoning body (sector grouping, effect creation, fetch simulation, persist) stays identical to the current implementation. Only the top guard section changes.

Run: `cd backend && python -m pytest tests/api/test_thinking_cas.py -v` — 2 PASS

- [ ] **Step 5: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

Expected: all tests PASS, no regressions
