from motor.motor_asyncio import AsyncIOMotorCollection


class ThinkingRepo:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def create(self, session: dict) -> str:
        await self.collection.insert_one(session)
        return session["id"]

    async def get(self, session_id: str) -> dict | None:
        return await self.collection.find_one({"id": session_id}, {"_id": 0})

    async def update(self, session_id: str, update: dict) -> bool:
        result = await self.collection.update_one({"id": session_id}, {"$set": update})
        return result.matched_count > 0

    async def add_nodes(self, session_id: str, nodes: list[dict]) -> int:
        await self.collection.update_one(
            {"id": session_id}, {"$push": {"nodes": {"$each": nodes}}}
        )
        return len(nodes)

    async def add_edges(self, session_id: str, edges: list[dict]) -> int:
        await self.collection.update_one(
            {"id": session_id}, {"$push": {"edges": {"$each": edges}}}
        )
        return len(edges)

    async def update_node_selection(
        self, session_id: str, node_id: str, selected: bool
    ) -> bool:
        result = await self.collection.update_one(
            {"id": session_id, "nodes.id": node_id},
            {"$set": {"nodes.$.selected": selected}},
        )
        return result.modified_count > 0
