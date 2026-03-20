from src.database.mongodb import mongodb
from src.database.repositories.graph_repo import GraphRepo
from src.database.repositories.node_repo import NodeRepo
from src.services.graph_service import GraphService


def get_graph_service() -> GraphService:
    graph_repo = GraphRepo(mongodb.get_collection("graphs"))
    node_repo = NodeRepo(mongodb.get_collection("layers"))
    return GraphService(graph_repo, node_repo)
