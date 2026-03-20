from src.database.repositories.graph_repo import GraphRepo
from src.database.repositories.node_repo import NodeRepo


class GraphService:
    def __init__(self, graph_repo: GraphRepo, node_repo: NodeRepo):
        self.graph_repo = graph_repo
        self.node_repo = node_repo

    async def get_graph(self, date: str, market: str = "US") -> dict | None:
        return await self.graph_repo.get_by_date(date, market)

    async def get_available_dates(self) -> list[str]:
        return await self.graph_repo.list_dates()

    async def get_node_layers(self, node_id: str) -> list[dict] | None:
        layers = await self.node_repo.get_layers(node_id)
        return layers if layers else None
