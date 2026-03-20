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

def create_sample_graph() -> dict:
    """Produces a complete graph matching the API response shape."""
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

- [ ] **Step 2: Write contract test**

```python
# tests/functional/test_graph_contract.py
from src.models.factories import create_sample_graph

def test_graph_response_has_required_fields():
    data = create_sample_graph()
    assert "date" in data
    assert "market" in data
    assert "nodes" in data
    assert "edges" in data

def test_nodes_have_required_fields():
    data = create_sample_graph()
    required = {"id", "type", "surface_summary", "direction", "confidence"}
    for node in data["nodes"]:
        assert required.issubset(node.keys()), f"Missing: {required - node.keys()}"

def test_edges_have_required_fields():
    data = create_sample_graph()
    for edge in data["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "label" in edge

def test_node_types_are_valid():
    valid = {"news_event", "impact", "stock_endpoint",
             "value_opportunity", "reason", "convergence"}
    data = create_sample_graph()
    for node in data["nodes"]:
        assert node["type"] in valid

def test_directions_are_valid():
    valid = {"bullish", "bearish", "neutral"}
    data = create_sample_graph()
    for node in data["nodes"]:
        assert node["direction"] in valid
```

- [ ] **Step 3: Run tests — verify they pass**

Run: `cd backend && python -m pytest tests/functional/test_graph_contract.py -v`

- [ ] **Step 4: Commit**

```bash
git commit -m "test: data contract verification — graph response shape validation"
```
