import pytest
from src.models.graph import DailyGraph
from src.models.node import Node, Layer, Edge, NodeType, Direction


def test_daily_graph_creation():
    graph = DailyGraph(date="2026-03-20", market="US")
    assert graph.status == "pending"
    assert graph.market == "US"


def test_daily_graph_requires_valid_market():
    with pytest.raises(ValueError):
        DailyGraph(date="2026-03-20", market="INVALID")


def test_node_creation():
    node = Node(
        graph_id="g1",
        type=NodeType.NEWS_EVENT,
        surface_summary="Fed holds rates",
        direction=Direction.BULLISH,
        confidence=82.0,
    )
    assert node.type == NodeType.NEWS_EVENT
    assert node.confidence == 82.0


def test_node_generates_id():
    node = Node(
        graph_id="g1",
        type=NodeType.IMPACT,
        surface_summary="test",
        direction=Direction.NEUTRAL,
        confidence=50.0,
    )
    assert node.id is not None and len(node.id) > 0


def test_layer_creation():
    layer = Layer(node_id="n1", depth=0, content="Summary text")
    assert layer.depth == 0


def test_layer_depth_validation():
    with pytest.raises(ValueError):
        Layer(node_id="n1", depth=5, content="Bad depth")


def test_layer_depth_accepts_0_through_3():
    for d in range(4):
        layer = Layer(node_id="n1", depth=d, content=f"Layer {d}")
        assert layer.depth == d


def test_edge_creation():
    edge = Edge(source="n1", target="n2", label="impacts")
    assert edge.label == "impacts"


def test_direction_enum_values():
    assert Direction.BULLISH.value == "bullish"
    assert Direction.BEARISH.value == "bearish"
    assert Direction.NEUTRAL.value == "neutral"


def test_node_type_enum_values():
    assert NodeType.NEWS_EVENT.value == "news_event"
    assert NodeType.CONVERGENCE.value == "convergence"
    assert NodeType.STOCK_ENDPOINT.value == "stock_endpoint"
