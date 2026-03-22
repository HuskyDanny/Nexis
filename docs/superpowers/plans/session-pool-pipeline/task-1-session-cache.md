### Task 1: Redis Client + Session Cache Service

**Parent:** [Session & Pool Pipeline Plan](../2026-03-22-session-pool-entity-pipeline.md)

**Files:**
- Modify: `backend/src/database/redis.py`, `backend/src/models/thinking.py`, `backend/src/core/config.py`
- Create: `backend/src/services/session_cache.py`
- Test: `backend/tests/test_redis_client.py`, `backend/tests/test_session_cache.py`

---

- [ ] **Step 1: Write failing tests for RedisClient — `backend/tests/test_redis_client.py`**

```python
from unittest.mock import AsyncMock
import pytest
from src.database.redis import RedisClient

@pytest.fixture
def redis():
    client = RedisClient()
    client.client = AsyncMock()
    return client

async def test_delete_calls_client(redis):
    redis.client.delete.return_value = 1
    assert await redis.delete("session:abc:meta") == 1
    redis.client.delete.assert_awaited_once_with("session:abc:meta")

async def test_delete_raises_when_disconnected():
    with pytest.raises(RuntimeError, match="Redis not connected"):
        await RedisClient().delete("key")

async def test_hset_calls_client(redis):
    redis.client.hset.return_value = 1
    assert await redis.hset("k", {"a": "b"}) == 1
    redis.client.hset.assert_awaited_once_with("k", mapping={"a": "b"})

async def test_hget_calls_client(redis):
    redis.client.hget.return_value = "idle"
    assert await redis.hget("k", "status") == "idle"

async def test_hgetall_calls_client(redis):
    redis.client.hgetall.return_value = {"status": "idle"}
    assert await redis.hgetall("k") == {"status": "idle"}

async def test_expire_calls_client(redis):
    redis.client.expire.return_value = True
    assert await redis.expire("k", 3600) is True

async def test_all_raise_when_disconnected():
    c = RedisClient()
    for coro in [c.hset("k", {}), c.hget("k", "f"), c.hgetall("k"), c.expire("k", 1)]:
        with pytest.raises(RuntimeError):
            await coro
```

Run: `cd backend && python -m pytest tests/test_redis_client.py -v` — expect FAIL.

- [ ] **Step 2: Implement RedisClient methods — `backend/src/database/redis.py`**

Add `_check_connected` helper, then add `delete`, `hset`, `hget`, `hgetall`, `expire`:

```python
import redis.asyncio as redis

class RedisClient:
    def __init__(self):
        self.client: redis.Redis | None = None

    async def connect(self, url: str):
        self.client = redis.from_url(url, decode_responses=True)
        await self.client.ping()

    async def close(self):
        if self.client:
            await self.client.close()

    def _check(self):
        if self.client is None:
            raise RuntimeError("Redis not connected")

    async def get(self, key: str) -> str | None:
        self._check()
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None):
        self._check()
        await self.client.set(key, value, ex=ttl)

    async def delete(self, *keys: str) -> int:
        self._check()
        return await self.client.delete(*keys)

    async def hset(self, key: str, mapping: dict) -> int:
        self._check()
        return await self.client.hset(key, mapping=mapping)

    async def hget(self, key: str, field: str) -> str | None:
        self._check()
        return await self.client.hget(key, field)

    async def hgetall(self, key: str) -> dict:
        self._check()
        return await self.client.hgetall(key)

    async def expire(self, key: str, seconds: int) -> bool:
        self._check()
        return await self.client.expire(key, seconds)

redis_client = RedisClient()
```

Run: `cd backend && python -m pytest tests/test_redis_client.py -v` — expect PASS.

- [ ] **Step 3: Add `version` to ThinkingSession + `SessionConfig` to config**

In `thinking.py`, add `version: int = 1` to `ThinkingSession` (between `current_layer` and `error`).

In `config.py`:
```python
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class SessionConfig(BaseModel):
    cache_ttl_seconds: int = 3600
    key_prefix: str = "session"

class Settings(BaseSettings):
    # ... existing fields ...
    session: SessionConfig = SessionConfig()
    model_config = {"env_file": ".env.base", "env_file_encoding": "utf-8"}
```

Run existing tests: `python -m pytest tests/test_thinking_models.py -v` — expect PASS.

- [ ] **Step 4: Write failing tests — `backend/tests/test_session_cache.py`**

```python
import json
from unittest.mock import AsyncMock
import pytest
from src.services.session_cache import SessionCache
from src.core.config import SessionConfig

@pytest.fixture
def mock_redis():
    return AsyncMock()

@pytest.fixture
def cache(mock_redis):
    return SessionCache(redis=mock_redis, config=SessionConfig(cache_ttl_seconds=600))

async def test_write_stores_meta_nodes_edges(cache, mock_redis):
    session = {
        "id": "abc", "date": "2026-03-22", "market": "US", "status": "idle",
        "version": 1, "current_layer": 0, "max_depth": 3, "error": None,
        "nodes": [{"id": "n1"}], "edges": [{"source": "n1", "target": "n2"}],
    }
    await cache.write(session)
    assert mock_redis.hset.await_count == 1
    assert mock_redis.set.await_count == 2
    assert mock_redis.expire.await_count == 3

async def test_read_meta_returns_parsed(cache, mock_redis):
    mock_redis.hgetall.return_value = {
        "date": "2026-03-22", "market": "US", "status": "idle",
        "version": "1", "current_layer": "0", "max_depth": "3", "error": "",
    }
    result = await cache.read_meta("abc")
    assert result["version"] == 1
    assert result["market"] == "US"

async def test_read_meta_returns_none_on_empty(cache, mock_redis):
    mock_redis.hgetall.return_value = {}
    assert await cache.read_meta("x") is None

async def test_read_nodes(cache, mock_redis):
    mock_redis.get.return_value = json.dumps([{"id": "n1"}])
    assert await cache.read_nodes("abc") == [{"id": "n1"}]

async def test_read_nodes_miss(cache, mock_redis):
    mock_redis.get.return_value = None
    assert await cache.read_nodes("abc") == []

async def test_invalidate(cache, mock_redis):
    await cache.invalidate("abc")
    mock_redis.delete.assert_awaited_once_with(
        "session:abc:meta", "session:abc:nodes", "session:abc:edges",
    )
```

Run: `cd backend && python -m pytest tests/test_session_cache.py -v` — expect FAIL.

- [ ] **Step 5: Implement SessionCache — `backend/src/services/session_cache.py`**

```python
import json
from src.core.config import SessionConfig

class SessionCache:
    META_FIELDS = ("date", "market", "status", "version", "current_layer", "max_depth", "error")
    INT_FIELDS = ("version", "current_layer", "max_depth")

    def __init__(self, redis, config: SessionConfig):
        self.redis = redis
        self.prefix = config.key_prefix
        self.ttl = config.cache_ttl_seconds

    def _key(self, sid: str, suffix: str) -> str:
        return f"{self.prefix}:{sid}:{suffix}"

    async def write(self, session: dict) -> None:
        sid = session["id"]
        meta = {f: str(session.get(f, "")) for f in self.META_FIELDS}
        await self.redis.hset(self._key(sid, "meta"), mapping=meta)
        await self.redis.set(self._key(sid, "nodes"), json.dumps(session.get("nodes", [])))
        await self.redis.set(self._key(sid, "edges"), json.dumps(session.get("edges", [])))
        for s in ("meta", "nodes", "edges"):
            await self.redis.expire(self._key(sid, s), self.ttl)

    async def read_meta(self, sid: str) -> dict | None:
        data = await self.redis.hgetall(self._key(sid, "meta"))
        if not data:
            return None
        for f in self.INT_FIELDS:
            if f in data:
                data[f] = int(data[f])
        return data

    async def read_nodes(self, sid: str) -> list[dict]:
        raw = await self.redis.get(self._key(sid, "nodes"))
        return json.loads(raw) if raw else []

    async def read_edges(self, sid: str) -> list[dict]:
        raw = await self.redis.get(self._key(sid, "edges"))
        return json.loads(raw) if raw else []

    async def invalidate(self, sid: str) -> None:
        await self.redis.delete(
            self._key(sid, "meta"), self._key(sid, "nodes"), self._key(sid, "edges"),
        )
```

Run: `cd backend && python -m pytest tests/test_session_cache.py tests/test_redis_client.py -v` — expect PASS.

- [ ] **Step 6: Run all tests and commit**

```bash
cd backend && python -m pytest tests/test_redis_client.py tests/test_session_cache.py tests/test_thinking_models.py -v
```

Commit: `feat(session-cache): add Redis hash ops + write-aside SessionCache with split keys`
