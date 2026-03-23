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
