"""Tests for API error paths — 4xx and 5xx responses.

Covers Gate 6.3: error responses on critical endpoints have correct
status codes and match the ErrorResponse shape.
"""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.dependencies import get_graph_service


@pytest.fixture
def client():
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

        from src.main import app

        yield TestClient(app, raise_server_exceptions=False)


def _assert_error_shape(resp):
    """Verify response matches ErrorResponse model."""
    body = resp.json()
    assert "error" in body, f"Missing 'error' key in {body}"
    assert "request_id" in body, f"Missing 'request_id' key in {body}"


class TestThinkingErrorPaths:
    def test_get_nonexistent_session_returns_404(self, client):
        with patch("src.api.thinking.mongodb") as mock_mongo:
            mock_col = AsyncMock()
            mock_col.find_one = AsyncMock(return_value=None)
            mock_mongo.get_collection.return_value = mock_col

            resp = client.get("/api/thinking/nonexistent-session")
            assert resp.status_code == 404
            _assert_error_shape(resp)

    def test_step_on_nonexistent_session_returns_404(self, client):
        with patch("src.api.thinking.mongodb") as mock_mongo:
            mock_col = AsyncMock()
            mock_col.find_one = AsyncMock(return_value=None)
            mock_col.find_one_and_update = AsyncMock(return_value=None)
            mock_mongo.get_collection.return_value = mock_col

            resp = client.post("/api/thinking/nonexistent/step")
            assert resp.status_code == 404
            _assert_error_shape(resp)

    def test_match_on_nonexistent_session_returns_404(self, client):
        with patch("src.api.thinking.mongodb") as mock_mongo:
            mock_col = AsyncMock()
            mock_col.find_one = AsyncMock(return_value=None)
            mock_mongo.get_collection.return_value = mock_col

            resp = client.post("/api/thinking/nonexistent/match")
            assert resp.status_code == 404
            _assert_error_shape(resp)

    def test_toggle_node_on_nonexistent_session_returns_404(self, client):
        with patch("src.api.thinking.mongodb") as mock_mongo:
            mock_col = AsyncMock()
            mock_col.find_one = AsyncMock(return_value=None)
            mock_col.find_one_and_update = AsyncMock(return_value=None)
            mock_mongo.get_collection.return_value = mock_col

            resp = client.patch(
                "/api/thinking/nonexistent/node/n1",
                json={"selected": True},
            )
            assert resp.status_code == 404
            _assert_error_shape(resp)


class TestNodesErrorPaths:
    def test_get_layers_nonexistent_node_returns_404(self, client):
        from src.main import app

        mock_service = AsyncMock()
        mock_service.get_node_layers = AsyncMock(return_value=None)
        app.dependency_overrides[get_graph_service] = lambda: mock_service
        try:
            resp = client.get("/api/nodes/nonexistent/layers")
            assert resp.status_code == 404
            _assert_error_shape(resp)
        finally:
            app.dependency_overrides.pop(get_graph_service, None)


class TestPoolsErrorPaths:
    def test_get_pools_returns_empty_on_no_data(self, client):
        """Pools endpoint returns empty lists, not 404, when no data exists."""
        with patch("src.api.pools.mongodb") as mock_mongo:
            mock_col = AsyncMock()
            mock_col.find_one = AsyncMock(return_value=None)
            mock_mongo.get_collection.return_value = mock_col

            resp = client.get("/api/pools/live/2099-01-01")
            # Should return 200 with empty pools, not error
            assert resp.status_code == 200


class TestValidationErrors:
    def test_thinking_start_missing_date_returns_422(self, client):
        resp = client.post("/api/thinking", json={"market": "US"})
        assert resp.status_code == 422

    def test_thinking_auto_missing_date_returns_422(self, client):
        resp = client.post("/api/thinking/auto", json={"market": "US"})
        assert resp.status_code == 422

    def test_toggle_node_missing_body_returns_422(self, client):
        resp = client.patch("/api/thinking/sess1/node/n1", json={})
        assert resp.status_code == 422
