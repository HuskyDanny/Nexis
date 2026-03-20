import pytest
from src.models.thinking import (
    ThinkingNode,
    ThinkingNodeType,
    ThinkingEdge,
    ThinkingSession,
    SessionStatus,
    validate_acyclicity,
)


def test_thinking_node_creation_with_defaults():
    node = ThinkingNode(type=ThinkingNodeType.NEWS, content="Fed holds rates")
    assert node.type == ThinkingNodeType.NEWS
    assert node.content == "Fed holds rates"
    assert node.layer == 0
    assert node.reasoning == ""
    assert node.sources == []
    assert node.parents == []
    assert node.selected is True
    assert node.metadata == {}
    assert len(node.id) == 12


def test_thinking_node_with_explicit_values():
    node = ThinkingNode(
        id="custom_id_12",
        layer=2,
        type=ThinkingNodeType.EFFECT,
        content="Rate hike impact",
        reasoning="Higher rates reduce borrowing",
        sources=["https://fed.gov"],
        parents=["abc123"],
        selected=False,
        metadata={"severity": "high"},
    )
    assert node.id == "custom_id_12"
    assert node.layer == 2
    assert node.reasoning == "Higher rates reduce borrowing"
    assert node.sources == ["https://fed.gov"]
    assert node.parents == ["abc123"]
    assert node.selected is False
    assert node.metadata == {"severity": "high"}


def test_thinking_node_type_enum_values():
    assert ThinkingNodeType.NEWS.value == "news"
    assert ThinkingNodeType.EFFECT.value == "effect"
    assert ThinkingNodeType.FETCH.value == "fetch"
    assert ThinkingNodeType.OPPORTUNITY.value == "opportunity"


def test_thinking_edge_creation():
    edge = ThinkingEdge(source="n1", target="n2", relationship="causes")
    assert edge.source == "n1"
    assert edge.target == "n2"
    assert edge.relationship == "causes"


def test_session_status_enum_values():
    assert SessionStatus.IDLE.value == "idle"
    assert SessionStatus.THINKING.value == "thinking"
    assert SessionStatus.PAUSED.value == "paused"
    assert SessionStatus.COMPLETE.value == "complete"
    assert SessionStatus.ERROR.value == "error"


def test_thinking_session_creation_with_defaults():
    session = ThinkingSession(date="2026-03-20")
    assert session.date == "2026-03-20"
    assert session.market == "US"
    assert session.max_depth == 3
    assert session.nodes == []
    assert session.edges == []
    assert session.status == SessionStatus.IDLE
    assert session.current_layer == 0
    assert session.error is None
    assert session.created_at is not None
    assert len(session.id) == 12


def test_thinking_session_with_nodes_and_edges():
    node = ThinkingNode(type=ThinkingNodeType.NEWS, content="Oil price spike")
    edge = ThinkingEdge(source=node.id, target="other", relationship="causes")
    session = ThinkingSession(
        date="2026-03-20",
        market="CN",
        nodes=[node],
        edges=[edge],
        status=SessionStatus.THINKING,
        current_layer=1,
    )
    assert len(session.nodes) == 1
    assert len(session.edges) == 1
    assert session.market == "CN"
    assert session.status == SessionStatus.THINKING
    assert session.current_layer == 1


def test_thinking_session_unique_ids():
    s1 = ThinkingSession(date="2026-03-20")
    s2 = ThinkingSession(date="2026-03-20")
    assert s1.id != s2.id


def test_thinking_node_unique_ids():
    n1 = ThinkingNode(type=ThinkingNodeType.FETCH, content="a")
    n2 = ThinkingNode(type=ThinkingNodeType.FETCH, content="b")
    assert n1.id != n2.id


# --- Acyclicity validation ---


def test_validate_acyclicity_valid_edges():
    nodes = [
        ThinkingNode(id="a", layer=0, type=ThinkingNodeType.NEWS, content="x"),
        ThinkingNode(id="b", layer=1, type=ThinkingNodeType.EFFECT, content="y"),
        ThinkingNode(id="c", layer=2, type=ThinkingNodeType.OPPORTUNITY, content="z"),
    ]
    edges = [
        ThinkingEdge(source="a", target="b", relationship="causes"),
        ThinkingEdge(source="b", target="c", relationship="matches"),
    ]
    assert validate_acyclicity(nodes, edges) is True


def test_validate_acyclicity_rejects_same_layer():
    nodes = [
        ThinkingNode(id="a", layer=0, type=ThinkingNodeType.NEWS, content="x"),
        ThinkingNode(id="b", layer=0, type=ThinkingNodeType.NEWS, content="y"),
    ]
    edges = [ThinkingEdge(source="a", target="b", relationship="causes")]
    assert validate_acyclicity(nodes, edges) is False


def test_validate_acyclicity_rejects_backward_edge():
    nodes = [
        ThinkingNode(id="a", layer=0, type=ThinkingNodeType.NEWS, content="x"),
        ThinkingNode(id="b", layer=1, type=ThinkingNodeType.EFFECT, content="y"),
    ]
    edges = [ThinkingEdge(source="b", target="a", relationship="causes")]
    assert validate_acyclicity(nodes, edges) is False


def test_validate_acyclicity_empty_edges():
    nodes = [
        ThinkingNode(id="a", layer=0, type=ThinkingNodeType.NEWS, content="x"),
    ]
    assert validate_acyclicity(nodes, []) is True
