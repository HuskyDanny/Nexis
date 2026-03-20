# Task 2: Data Layer

**Files:**
- Create: `backend/src/database/mongodb.py`
- Create: `backend/src/database/redis.py`
- Create: `backend/src/models/graph.py`
- Create: `backend/src/models/node.py`
- Create: `backend/src/models/annotation.py`
- Create: `backend/src/models/pipeline.py`
- Create: `backend/src/database/repositories/graph_repo.py`
- Create: `backend/src/database/repositories/node_repo.py`
- Test: `backend/tests/test_models.py`

---

- [ ] **Step 1: Write failing tests for Pydantic models**

```python
from src.models.graph import DailyGraph
from src.models.node import Node, Layer, NodeType, Direction

def test_daily_graph_creation():
    graph = DailyGraph(date="2026-03-20", market="US")
    assert graph.status == "pending"

def test_node_creation():
    node = Node(
        graph_id="g1", type=NodeType.NEWS_EVENT,
        surface_summary="Fed holds rates",
        direction=Direction.BULLISH, confidence=82.0
    )
    assert node.type == NodeType.NEWS_EVENT

def test_layer_depth_validation():
    layer = Layer(node_id="n1", depth=0, content="Summary")
    assert layer.depth == 0

def test_layer_depth_out_of_range():
    import pytest
    with pytest.raises(ValueError):
        Layer(node_id="n1", depth=5, content="Bad")
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd backend && python -m pytest tests/test_models.py -v`

- [ ] **Step 3: Implement MongoDB connection manager**

```python
# database/mongodb.py
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

class MongoDB:
    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.db: AsyncIOMotorDatabase | None = None

    async def connect(self, url: str):
        self.client = AsyncIOMotorClient(url)
        db_name = url.rsplit("/", 1)[-1].split("?")[0]
        self.db = self.client[db_name]
        await self.db.command("ping")

    async def close(self):
        if self.client:
            self.client.close()

    def get_collection(self, name: str):
        return self.db[name]

mongodb = MongoDB()
```

- [ ] **Step 4: Implement Redis client wrapper**

- [ ] **Step 5: Implement Pydantic models**

Key models with enums:
- `NodeType`: NEWS_EVENT, IMPACT, STOCK_ENDPOINT, VALUE_OPPORTUNITY, REASON, CONVERGENCE
- `Direction`: BULLISH, BEARISH, NEUTRAL
- `DailyGraph`: date, market (CN/US), status (pending/complete/failed), nodes, edges
- `Node`: id, graph_id, type, surface_summary, direction, confidence
- `Layer`: node_id, depth (0-3 validated), content, tool_outputs, sources
- `Edge`: source_node, target_node, label, relationship_type
- `Annotation`: node_id, user_id, text, tags[], created_at
- `PipelineRun`: date, market, duration, node_count, error_count, cost, step_scores

- [ ] **Step 6: Implement graph_repo and node_repo**

Repository pattern with async Motor:
- `GraphRepo.get_by_date(date, market)` → DailyGraph | None
- `GraphRepo.upsert(graph)` → str (graph_id)
- `GraphRepo.list_dates()` → list[str]
- `NodeRepo.get_layers(node_id)` → list[Layer]
- `NodeRepo.bulk_insert(nodes)` → list[str]

- [ ] **Step 7: Run tests — verify they pass**

Run: `cd backend && python -m pytest tests/test_models.py -v`

- [ ] **Step 8: Commit**

```bash
git add backend/ && git commit -m "feat: data layer — MongoDB, Redis, models, repositories"
```
