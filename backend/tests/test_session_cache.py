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
        "id": "abc",
        "date": "2026-03-22",
        "market": "US",
        "status": "idle",
        "version": 1,
        "current_layer": 0,
        "max_depth": 3,
        "error": None,
        "nodes": [{"id": "n1"}],
        "edges": [{"source": "n1", "target": "n2"}],
    }
    await cache.write(session)
    assert mock_redis.hset.await_count == 1
    assert mock_redis.set.await_count == 2
    assert mock_redis.expire.await_count == 3


async def test_read_meta_returns_parsed(cache, mock_redis):
    mock_redis.hgetall.return_value = {
        "date": "2026-03-22",
        "market": "US",
        "status": "idle",
        "version": "1",
        "current_layer": "0",
        "max_depth": "3",
        "error": "",
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
        "session:abc:meta",
        "session:abc:nodes",
        "session:abc:edges",
    )
