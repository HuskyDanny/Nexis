from motor.motor_asyncio import AsyncIOMotorCollection


class NodeRepo:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def get_layers(self, node_id: str) -> list[dict]:
        cursor = self.collection.find({"node_id": node_id}, {"_id": 0}).sort("depth", 1)
        return await cursor.to_list(length=10)

    async def bulk_insert(self, layers: list[dict]) -> int:
        if not layers:
            return 0
        result = await self.collection.insert_many(layers)
        return len(result.inserted_ids)
