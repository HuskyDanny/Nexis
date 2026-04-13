"""Tests for nodes API endpoints.

Covers:
- GET /api/nodes/{node_id}/layers — returns layers for a node
- 404 when node not found
"""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.dependencies import get_graph_service


@pytest.fixture
def client():
    mock_service = AsyncMock()

    from src.main import app

    app.dependency_overrides[get_graph_service] = lambda: mock_service

    with (
        patch("src.main.mongodb") as mock_mongo,
        patch("src.main.redis_client") as mock_redis,
    ):
        mock_mongo.connect = AsyncMock()
        mock_mongo.close = AsyncMock()
        mock_col = AsyncMock()
        mock_col.update_many = AsyncMock(return_value=AsyncMock(modified_count=0))
        mock_mongo.get_collection.return_value = mock_col
        mock_redis.connect = AsyncMock()
        mock_redis.close = AsyncMock()

        yield TestClient(app, raise_server_exceptions=False), mock_service

    app.dependency_overrides.clear()


class TestGetLayers:
    def test_returns_layers_for_known_node(self, client):
        tc, mock_service = client
        mock_service.get_node_layers = AsyncMock(
            return_value=[
                {"layer": 1, "content": "Effect of rate hike", "confidence": 0.8}
            ]
        )
        resp = tc.get("/api/nodes/n1/layers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["layer"] == 1

    def test_returns_404_for_unknown_node(self, client):
        tc, mock_service = client
        mock_service.get_node_layers = AsyncMock(return_value=None)
        resp = tc.get("/api/nodes/unknown-id/layers")
        assert resp.status_code == 404

    def test_404_response_has_error_shape(self, client):
        """Error responses should match ErrorResponse model."""
        tc, mock_service = client
        mock_service.get_node_layers = AsyncMock(return_value=None)
        resp = tc.get("/api/nodes/unknown-id/layers")
        body = resp.json()
        assert "error" in body
        assert "request_id" in body
