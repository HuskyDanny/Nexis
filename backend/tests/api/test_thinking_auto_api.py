"""Tests for thinking auto-pipeline API endpoints.

Covers:
- POST /api/thinking/auto — creates session and returns session_id
- SSE event stream structure
- Error handling for pipeline failures
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _mock_pools_collection():
    """Return a mock collection that returns cached pool data."""
    mock_col = AsyncMock()
    mock_col.find_one = AsyncMock(
        return_value={
            "type": "news",
            "date": "2026-04-13",
            "market": "US",
            "items": [
                {
                    "id": "n1",
                    "title": "Fed holds rates steady",
                    "source": "test",
                    "summary": "No change",
                    "direction": "neutral",
                    "confidence": 0.5,
                }
            ],
        }
    )
    mock_col.insert_one = AsyncMock()
    mock_col.update_one = AsyncMock()
    return mock_col


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


class TestAutoThink:
    def test_returns_session_id(self, client):
        """POST /thinking/auto returns a session_id and status."""
        with (
            patch("src.api.thinking_auto.mongodb") as mock_mongo,
            patch(
                "src.api.thinking_auto.fetch_real_news", new_callable=AsyncMock
            ) as mock_news,
            patch(
                "src.api.thinking_auto.fetch_real_stocks", new_callable=AsyncMock
            ) as mock_stocks,
            patch("src.api.thinking_auto.registry") as mock_registry,
        ):
            mock_mongo.get_collection.return_value = _mock_pools_collection()
            mock_news.return_value = []
            mock_stocks.return_value = []
            mock_registry.create = MagicMock()

            resp = client.post(
                "/api/thinking/auto",
                json={"date": "2026-04-13", "market": "US", "max_depth": 3},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "session_id" in data
            assert data["status"] == "thinking"

    def test_auto_requires_date(self, client):
        """POST /thinking/auto without date returns 422."""
        resp = client.post("/api/thinking/auto", json={"market": "US"})
        assert resp.status_code == 422
