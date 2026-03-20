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

    async def get(self, key: str) -> str | None:
        if self.client is None:
            raise RuntimeError("Redis not connected")
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None):
        if self.client is None:
            raise RuntimeError("Redis not connected")
        await self.client.set(key, value, ex=ttl)


redis_client = RedisClient()
