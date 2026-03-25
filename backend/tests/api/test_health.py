import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    from src.main import app

    with (
        patch("src.main.mongodb") as mock_mongo,
        patch("src.main.redis_client") as mock_redis,
    ):
        # Mock lifespan dependencies so app starts without real connections
        mock_mongo.connect = AsyncMock()
        mock_mongo.close = AsyncMock()
        mock_col = AsyncMock()
        mock_col.update_many = AsyncMock(return_value=AsyncMock(modified_count=0))
        mock_mongo.get_collection.return_value = mock_col
        mock_redis.connect = AsyncMock()
        mock_redis.close = AsyncMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.mark.asyncio
async def test_liveness_returns_ok(client):
    """Liveness probe — no dependency checks, always returns 200."""
    resp = await client.get("/api/health/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_returns_ok_when_deps_healthy(client):
    """Readiness probe — checks MongoDB + Redis."""
    with (
        patch("src.api.health.mongodb") as mock_mongo,
        patch("src.api.health.redis_client") as mock_redis,
    ):
        mock_mongo.db = AsyncMock()
        mock_mongo.db.command = AsyncMock(return_value={"ok": 1})
        mock_redis.client = AsyncMock()
        mock_redis.client.ping = AsyncMock(return_value=True)

        resp = await client.get("/api/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["mongodb"] == "ok"
        assert data["redis"] == "ok"


@pytest.mark.asyncio
async def test_readiness_returns_503_when_mongo_down(client):
    """Readiness probe returns 503 if MongoDB is unreachable."""
    with (
        patch("src.api.health.mongodb") as mock_mongo,
        patch("src.api.health.redis_client") as mock_redis,
    ):
        mock_mongo.db = AsyncMock()
        mock_mongo.db.command = AsyncMock(side_effect=Exception("connection refused"))
        mock_redis.client = AsyncMock()
        mock_redis.client.ping = AsyncMock(return_value=True)

        resp = await client.get("/api/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert "error" in data["mongodb"]


@pytest.mark.asyncio
async def test_readiness_returns_503_when_redis_down(client):
    """Readiness probe returns 503 if Redis is unreachable."""
    with (
        patch("src.api.health.mongodb") as mock_mongo,
        patch("src.api.health.redis_client") as mock_redis,
    ):
        mock_mongo.db = AsyncMock()
        mock_mongo.db.command = AsyncMock(return_value={"ok": 1})
        mock_redis.client = None  # Not connected

        resp = await client.get("/api/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert "error" in data["redis"]


@pytest.mark.asyncio
async def test_startup_returns_ok(client):
    """Startup probe — same as liveness."""
    resp = await client.get("/api/health/startup")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_legacy_health_still_works(client):
    """Backward-compat: /api/health still returns 200."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
