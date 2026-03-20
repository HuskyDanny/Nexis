from src.models.factories import create_sample_graph_model


def test_serialized_graph_has_required_fields():
    graph = create_sample_graph_model()
    data = graph.model_dump(mode="json")
    assert "date" in data
    assert "market" in data
    assert "status" in data
    assert "nodes" in data
    assert "edges" in data


def test_serialized_nodes_have_required_fields():
    graph = create_sample_graph_model()
    data = graph.model_dump(mode="json")
    required = {"id", "type", "surface_summary", "direction", "confidence"}
    for node in data["nodes"]:
        assert required.issubset(node.keys()), f"Missing: {required - node.keys()}"


def test_serialized_node_types_are_strings():
    graph = create_sample_graph_model()
    data = graph.model_dump(mode="json")
    valid = {
        "news_event",
        "impact",
        "stock_endpoint",
        "value_opportunity",
        "reason",
        "convergence",
    }
    for node in data["nodes"]:
        assert isinstance(node["type"], str)
        assert node["type"] in valid


def test_serialized_directions_are_strings():
    graph = create_sample_graph_model()
    data = graph.model_dump(mode="json")
    valid = {"bullish", "bearish", "neutral"}
    for node in data["nodes"]:
        assert isinstance(node["direction"], str)
        assert node["direction"] in valid


def test_serialized_edges_have_required_fields():
    graph = create_sample_graph_model()
    data = graph.model_dump(mode="json")
    for edge in data["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "label" in edge


def test_market_serializes_as_string():
    graph = create_sample_graph_model()
    data = graph.model_dump(mode="json")
    assert data["market"] in ("CN", "US")
    assert isinstance(data["market"], str)


def test_status_serializes_as_string():
    graph = create_sample_graph_model()
    data = graph.model_dump(mode="json")
    assert data["status"] in ("pending", "complete", "failed")
    assert isinstance(data["status"], str)
