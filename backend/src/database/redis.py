import redis.asyncio as redis


class RedisClient:
    def __init__(self):
        self.client: redis.Redis | None = None

    def _check(self):
        if self.client is None:
            raise RuntimeError("Redis not connected")

    async def connect(self, url: str):
        self.client = redis.from_url(url, decode_responses=True)
        await self.client.ping()

    async def close(self):
        if self.client:
            await self.client.close()

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
