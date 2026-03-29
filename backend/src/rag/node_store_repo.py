"""MongoDB repository for the node_store collection."""

from __future__ import annotations

from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorCollection


class MongoNodeStoreRepo:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def insert(self, doc: dict) -> None:
        await self.collection.insert_one(doc)

    async def get(self, node_id: str) -> dict | None:
        return await self.collection.find_one({"id": node_id}, {"_id": 0})

    async def find_unindexed(self) -> list[dict]:
        cursor = self.collection.find({"indexed": False}, {"_id": 0})
        return await cursor.to_list(length=1000)

    async def find_ids_older_than(self, cutoff: datetime) -> list[str]:
        cursor = self.collection.find(
            {"created_at": {"$lt": cutoff}}, {"id": 1, "_id": 0}
        )
        docs = await cursor.to_list(length=10000)
        return [d["id"] for d in docs]

    async def delete_older_than(self, cutoff: datetime) -> int:
        result = await self.collection.delete_many({"created_at": {"$lt": cutoff}})
        return result.deleted_count

    async def mark_indexed(self, node_id: str, indexed: bool) -> None:
        await self.collection.update_one(
            {"id": node_id}, {"$set": {"indexed": indexed}}
        )

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("id", unique=True)
        await self.collection.create_index("session_id")
        await self.collection.create_index("indexed")
        await self.collection.create_index("created_at")
