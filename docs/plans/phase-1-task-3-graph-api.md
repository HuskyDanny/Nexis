# Task 3: Graph API Endpoints

**Files:**
- Create: `backend/src/api/graphs.py`
- Create: `backend/src/api/nodes.py`
- Create: `backend/src/services/graph_service.py`
- Modify: `backend/src/main.py` (register routers)
- Test: `backend/tests/api/test_graphs.py`

---

- [ ] **Step 1: Write failing tests for graph API**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_get_graph_missing_date_returns_404(client):
    resp = await client.get("/api/graphs/2026-03-20")
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_get_graph_dates_returns_list(client):
    resp = await client.get("/api/graphs/dates")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

@pytest.mark.asyncio
async def test_get_node_layers_missing_returns_404(client):
    resp = await client.get("/api/nodes/nonexistent/layers")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd backend && python -m pytest tests/api/test_graphs.py -v`

- [ ] **Step 3: Implement graph_service.py**

```python
# services/graph_service.py
class GraphService:
    def __init__(self, graph_repo, node_repo):
        self.graph_repo = graph_repo
        self.node_repo = node_repo

    async def get_graph(self, date: str, market: str = "US"):
        return await self.graph_repo.get_by_date(date, market)

    async def get_available_dates(self):
        return await self.graph_repo.list_dates()

    async def get_node_layers(self, node_id: str):
        return await self.node_repo.get_layers(node_id)
```

- [ ] **Step 4: Implement graphs.py router**

```python
# api/graphs.py
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/graphs", tags=["graphs"])

@router.get("/dates")
async def get_dates(service = Depends(get_graph_service)):
    return await service.get_available_dates()

@router.get("/{date}")
async def get_graph(date: str, market: str = "US", service = Depends(get_graph_service)):
    graph = await service.get_graph(date, market)
    if not graph:
        raise HTTPException(404, "No graph for this date")
    return graph
```

- [ ] **Step 5: Implement nodes.py router**

- [ ] **Step 6: Register routers in main.py**

- [ ] **Step 7: Run tests — verify they pass**

- [ ] **Step 8: Commit**

```bash
git commit -m "feat: graph API — GET graphs/:date, nodes/:id/layers, graphs/dates"
```
