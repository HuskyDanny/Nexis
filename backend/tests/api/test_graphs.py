import pytest
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_graph_service():
    """Create a mock GraphService with default return values."""
    service = MagicMock()
    service.get_graph = AsyncMock(return_value=None)
    service.get_available_dates = AsyncMock(return_value=["2026-03-20", "2026-03-19"])
    service.get_node_layers = AsyncMock(return_value=None)
    return service


@pytest.fixture
async def client(mock_graph_service):
    from src.api.dependencies import get_graph_service
    from src.main import app

    app.dependency_overrides[get_graph_service] = lambda: mock_graph_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_graph_missing_returns_404(client, mock_graph_service):
    mock_graph_service.get_graph = AsyncMock(return_value=None)
    resp = await client.get("/api/graphs/2026-03-20")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_graph_returns_data(client, mock_graph_service):
    mock_graph_service.get_graph = AsyncMock(
        return_value={
            "date": "2026-03-20",
            "market": "US",
            "status": "complete",
            "nodes": [],
            "edges": [],
        }
    )
    resp = await client.get("/api/graphs/2026-03-20")
    assert resp.status_code == 200
    body = resp.json()
    assert body["date"] == "2026-03-20"
    assert body["market"] == "US"


@pytest.mark.asyncio
async def test_get_graph_with_market_param(client, mock_graph_service):
    mock_graph_service.get_graph = AsyncMock(
        return_value={"date": "2026-03-20", "market": "CN", "nodes": [], "edges": []}
    )
    resp = await client.get("/api/graphs/2026-03-20?market=CN")
    assert resp.status_code == 200
    mock_graph_service.get_graph.assert_awaited_once_with("2026-03-20", "CN")


@pytest.mark.asyncio
async def test_get_graph_dates_returns_list(client, mock_graph_service):
    resp = await client.get("/api/graphs/dates")
    assert resp.status_code == 200
    assert resp.json() == ["2026-03-20", "2026-03-19"]


@pytest.mark.asyncio
async def test_get_node_layers_missing_returns_404(client, mock_graph_service):
    mock_graph_service.get_node_layers = AsyncMock(return_value=None)
    resp = await client.get("/api/nodes/nonexistent/layers")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_node_layers_returns_data(client, mock_graph_service):
    mock_graph_service.get_node_layers = AsyncMock(
        return_value=[
            {"node_id": "n1", "depth": 0, "content": "Summary"},
            {"node_id": "n1", "depth": 1, "content": "Details"},
        ]
    )
    resp = await client.get("/api/nodes/n1/layers")
    assert resp.status_code == 200
    layers = resp.json()
    assert len(layers) == 2
    assert layers[0]["depth"] == 0
    assert layers[1]["depth"] == 1
