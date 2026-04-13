"""Tests for RequestMiddleware — request ID assignment and header propagation."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.request_logging import RequestMiddleware


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestMiddleware)

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    return app


client = TestClient(_make_app())


class TestRequestIdHeader:
    def test_returns_x_request_id_in_response(self):
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        # Auto-generated: 12 hex chars from uuid4
        assert len(resp.headers["X-Request-ID"]) == 12

    def test_preserves_custom_request_id(self):
        resp = client.get("/ping", headers={"X-Request-ID": "custom-id-999"})
        assert resp.headers["X-Request-ID"] == "custom-id-999"

    def test_different_requests_get_different_ids(self):
        r1 = client.get("/ping")
        r2 = client.get("/ping")
        assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]
