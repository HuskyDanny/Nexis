from motor.motor_asyncio import AsyncIOMotorCollection


class NewsEntityRepo:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def upsert(self, entity: dict) -> None:
        await self.collection.replace_one({"id": entity["id"]}, entity, upsert=True)

    async def get_by_id(self, entity_id: str) -> dict | None:
        return await self.collection.find_one({"id": entity_id}, {"_id": 0})

    async def get_active(self, market: str) -> list[dict]:
        cursor = self.collection.find(
            {"status": "active", "market": market}, {"_id": 0}
        )
        return await cursor.to_list(length=None)

    async def get_all(self, market: str, include_stale: bool = False) -> list[dict]:
        q = (
            {"status": {"$in": ["active", "stale"]}, "market": market}
            if include_stale
            else {"status": "active", "market": market}
        )
        return await self.collection.find(q, {"_id": 0}).to_list(length=None)
