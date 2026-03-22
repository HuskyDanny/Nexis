import redis.asyncio as aioredis


class RedisClient:
    def __init__(self) -> None:
        self.client: aioredis.Redis | None = None

    def _connected(self) -> aioredis.Redis:
        """Return client or raise if not connected. Narrows type for Pyright."""
        if self.client is None:
            raise RuntimeError("Redis not connected")
        return self.client

    async def connect(self, url: str) -> None:
        self.client = aioredis.from_url(url, decode_responses=True)
        await self.client.ping()

    async def close(self) -> None:
        if self.client:
            await self.client.close()

    async def get(self, key: str) -> str | None:
        return await self._connected().get(key)  # type: ignore[return-value]

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        await self._connected().set(key, value, ex=ttl)

    async def delete(self, *keys: str) -> int:
        return await self._connected().delete(*keys)

    async def hset(self, key: str, mapping: dict) -> int:
        return await self._connected().hset(key, mapping=mapping)  # type: ignore[return-value]

    async def hget(self, key: str, field: str) -> str | None:
        return await self._connected().hget(key, field)  # type: ignore[return-value]

    async def hgetall(self, key: str) -> dict:
        return await self._connected().hgetall(key)  # type: ignore[return-value]

    async def expire(self, key: str, seconds: int) -> bool:
        return await self._connected().expire(key, seconds)


redis_client = RedisClient()
