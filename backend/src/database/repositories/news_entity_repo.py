from motor.motor_asyncio import AsyncIOMotorCollection


class NewsEntityRepo:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def upsert(self, entity: dict) -> None:
        await self.collection.replace_one({"id": entity["id"]}, entity, upsert=True)

    async def get_by_id(self, entity_id: str) -> dict | None:
        return await self.collection.find_one({"id": entity_id}, {"_id": 0})

    async def get_active(self, market: str | None = None) -> list[dict]:
        q: dict = {"status": "active"}
        if market is not None:
            q["market"] = market
        cursor = self.collection.find(q, {"_id": 0})
        return await cursor.to_list(length=None)

    async def get_all(
        self, market: str | None = None, include_stale: bool = False
    ) -> list[dict]:
        q: dict = (
            {"status": {"$in": ["active", "stale"]}}
            if include_stale
            else {"status": "active"}
        )
        if market is not None:
            q["market"] = market
        return await self.collection.find(q, {"_id": 0}).to_list(length=None)

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("scope")
        await self.collection.create_index("status")
