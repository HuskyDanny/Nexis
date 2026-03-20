from src.models.graph import DailyGraph, GraphStatus, Market
from src.models.node import Direction, Edge, Node, NodeType


def create_sample_graph_model() -> DailyGraph:
    """Produces a Pydantic DailyGraph — .model_dump() is the API contract."""
    return DailyGraph(
        date="2026-03-20",
        market=Market.US,
        status=GraphStatus.COMPLETE,
        nodes=[
            Node(
                id="n1",
                graph_id="g1",
                type=NodeType.NEWS_EVENT,
                surface_summary="Fed holds rates steady",
                direction=Direction.BULLISH,
                confidence=82.0,
            ),
            Node(
                id="n2",
                graph_id="g1",
                type=NodeType.IMPACT,
                surface_summary="Financial sector bullish",
                direction=Direction.BULLISH,
                confidence=75.0,
            ),
            Node(
                id="n3",
                graph_id="g1",
                type=NodeType.CONVERGENCE,
                surface_summary="JPM — high conviction",
                direction=Direction.BULLISH,
                confidence=87.0,
            ),
        ],
        edges=[
            Edge(source="n1", target="n2", label="impacts"),
            Edge(source="n2", target="n3", label="confirms"),
        ],
    )
