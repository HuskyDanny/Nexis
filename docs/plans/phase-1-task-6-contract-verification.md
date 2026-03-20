# Task 6: Data Contract Verification

**Files:**
- Create: `backend/tests/functional/test_graph_contract.py`
- Create: `backend/src/models/factories.py`

---

- [ ] **Step 1: Create factory for sample graph data**

```python
# models/factories.py
from src.models.graph import DailyGraph
from src.models.node import Node, Layer, Edge, NodeType, Direction

def create_sample_graph_model() -> "DailyGraph":
    """Produces a Pydantic DailyGraph — .model_dump() is the API contract."""
    from src.models.graph import DailyGraph
    from src.models.node import Node, Edge, NodeType, Direction
    # Build using actual Pydantic models, not raw dicts
    return DailyGraph(
        date="2026-03-20", market="US", status="complete",
        nodes=[
            Node(id="n1", graph_id="g1", type=NodeType.NEWS_EVENT,
                 surface_summary="Fed holds rates steady",
                 direction=Direction.BULLISH, confidence=82.0),
            Node(id="n2", graph_id="g1", type=NodeType.IMPACT,
                 surface_summary="Financial sector → bullish",
                 direction=Direction.BULLISH, confidence=75.0),
            Node(id="n3", graph_id="g1", type=NodeType.CONVERGENCE,
                 surface_summary="JPM — high conviction",
                 direction=Direction.BULLISH, confidence=87.0),
        ],
        edges=[
            Edge(source="n1", target="n2", label="impacts"),
            Edge(source="n2", target="n3", label="confirms"),
        ]
    )

def create_sample_graph_dict() -> dict:
    """Convenience: returns model_dump for backward compat."""
    return create_sample_graph_model().model_dump(mode="json")

# DEPRECATED: use create_sample_graph_model() instead
def create_sample_graph() -> dict:
    """Legacy — produces a hand-crafted dict. Prefer create_sample_graph_model()."""
    return {
        "date": "2026-03-20",
        "market": "US",
        "status": "complete",
        "nodes": [
            {
                "id": "n1", "type": "news_event",
                "surface_summary": "Fed holds rates steady",
                "direction": "bullish", "confidence": 82.0
            },
            {
                "id": "n2", "type": "impact",
                "surface_summary": "Financial sector → bullish",
                "direction": "bullish", "confidence": 75.0
            },
            {
                "id": "n3", "type": "convergence",
                "surface_summary": "JPM — high conviction",
                "direction": "bullish", "confidence": 87.0
            },
        ],
        "edges": [
            {"source": "n1", "target": "n2", "label": "impacts"},
            {"source": "n2", "target": "n3", "label": "confirms"},
        ]
    }
```

- [ ] **Step 2: Write contract test using Pydantic model serialization**

Tests validate that `.model_dump()` output matches the frontend's expected shape —
not hand-crafted dicts.

```python
# tests/functional/test_graph_contract.py
from src.models.factories import create_sample_graph_model

def test_serialized_graph_has_required_fields():
    """Verify Pydantic serialization produces the shape frontend expects."""
    graph = create_sample_graph_model()
    data = graph.model_dump(mode="json")
    assert "date" in data
    assert "market" in data
    assert "nodes" in data
    assert "edges" in data

def test_serialized_nodes_have_required_fields():
    graph = create_sample_graph_model()
    data = graph.model_dump(mode="json")
    required = {"id", "type", "surface_summary", "direction", "confidence"}
    for node in data["nodes"]:
        assert required.issubset(node.keys())

def test_serialized_node_types_are_strings():
    """Frontend expects string enum values, not Python enum objects."""
    graph = create_sample_graph_model()
    data = graph.model_dump(mode="json")
    valid = {"news_event", "impact", "stock_endpoint",
             "value_opportunity", "reason", "convergence"}
    for node in data["nodes"]:
        assert isinstance(node["type"], str)
        assert node["type"] in valid

def test_serialized_edges_have_required_fields():
    graph = create_sample_graph_model()
    data = graph.model_dump(mode="json")
    for edge in data["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "label" in edge
```

- [ ] **Step 3: Run tests — verify they pass**

Run: `cd backend && python -m pytest tests/functional/test_graph_contract.py -v`

- [ ] **Step 4: Commit**

```bash
git commit -m "test: data contract verification — graph response shape validation"
```
