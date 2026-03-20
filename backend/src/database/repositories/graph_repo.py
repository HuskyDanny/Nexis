from motor.motor_asyncio import AsyncIOMotorCollection


class GraphRepo:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def get_by_date(self, date: str, market: str = "US") -> dict | None:
        return await self.collection.find_one(
            {"date": date, "market": market}, {"_id": 0}
        )

    async def upsert(self, graph: dict) -> str:
        result = await self.collection.update_one(
            {"date": graph["date"], "market": graph["market"]},
            {"$set": graph},
            upsert=True,
        )
        return str(result.upserted_id or graph.get("date"))

    async def list_dates(self) -> list[str]:
        cursor = self.collection.find({}, {"date": 1, "_id": 0}).sort("date", -1)
        docs = await cursor.to_list(length=100)
        return [doc["date"] for doc in docs]
