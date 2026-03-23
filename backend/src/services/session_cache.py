import json
from src.core.config import SessionConfig


class SessionCache:
    META_FIELDS = (
        "date",
        "market",
        "status",
        "version",
        "current_layer",
        "max_depth",
        "error",
    )
    INT_FIELDS = ("version", "current_layer", "max_depth")

    def __init__(self, redis, config: SessionConfig):
        self.redis = redis
        self.prefix = config.key_prefix
        self.ttl = config.cache_ttl_seconds

    def _key(self, sid: str, suffix: str) -> str:
        return f"{self.prefix}:{sid}:{suffix}"

    async def write(self, session: dict) -> None:
        sid = session["id"]
        meta = {
            f: str(v) if (v := session.get(f)) is not None else ""
            for f in self.META_FIELDS
        }
        await self.redis.hset(self._key(sid, "meta"), mapping=meta)
        await self.redis.set(
            self._key(sid, "nodes"), json.dumps(session.get("nodes", []))
        )
        await self.redis.set(
            self._key(sid, "edges"), json.dumps(session.get("edges", []))
        )
        for s in ("meta", "nodes", "edges"):
            await self.redis.expire(self._key(sid, s), self.ttl)

    async def read_meta(self, sid: str) -> dict | None:
        data = await self.redis.hgetall(self._key(sid, "meta"))
        if not data:
            return None
        for f in self.INT_FIELDS:
            if f in data and data[f]:
                try:
                    data[f] = int(data[f])
                except (ValueError, TypeError):
                    data[f] = 0
        return data

    async def read_nodes(self, sid: str) -> list[dict]:
        raw = await self.redis.get(self._key(sid, "nodes"))
        return json.loads(raw) if raw else []

    async def read_edges(self, sid: str) -> list[dict]:
        raw = await self.redis.get(self._key(sid, "edges"))
        return json.loads(raw) if raw else []

    async def invalidate(self, sid: str) -> None:
        await self.redis.delete(
            self._key(sid, "meta"),
            self._key(sid, "nodes"),
            self._key(sid, "edges"),
        )
