"""Tests for global error handlers — ErrorResponse shape and request_id propagation."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.errors import register_exception_handlers
from src.middleware.request_logging import RequestMiddleware


def _make_app() -> FastAPI:
    """Build a minimal app with error handlers + middleware for testing."""
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(RequestMiddleware)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    @app.get("/not-found")
    async def not_found():
        raise HTTPException(status_code=404, detail="thing_not_found")

    @app.get("/ok")
    async def ok():
        return {"status": "ok"}

    return app


@pytest.fixture
def dev_client():
    """Client with development settings — leaks exception details."""
    with patch("src.api.errors.settings") as mock_settings:
        mock_settings.environment = "development"
        app = _make_app()
        yield TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def prod_client():
    """Client with production settings — hides exception details."""
    with patch("src.api.errors.settings") as mock_settings:
        mock_settings.environment = "production"
        app = _make_app()
        yield TestClient(app, raise_server_exceptions=False)


class TestUnhandledException:
    def test_returns_error_response_shape(self, dev_client):
        resp = dev_client.get("/boom")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] == "internal_error"
        assert "detail" in body
        assert "request_id" in body

    def test_dev_leaks_detail(self, dev_client):
        resp = dev_client.get("/boom")
        body = resp.json()
        assert "kaboom" in body["detail"]

    def test_prod_hides_detail(self, prod_client):
        resp = prod_client.get("/boom")
        body = resp.json()
        assert "kaboom" not in (body.get("detail") or "")
        assert body["detail"] == "An unexpected error occurred"


class TestHTTPException:
    def test_returns_error_response_shape(self, dev_client):
        resp = dev_client.get("/not-found")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "thing_not_found"
        assert "request_id" in body


class TestRequestIdPropagation:
    def test_request_id_in_error_response(self, dev_client):
        resp = dev_client.get("/boom", headers={"X-Request-ID": "test-req-123"})
        body = resp.json()
        assert body["request_id"] == "test-req-123"

    def test_request_id_in_http_error(self, dev_client):
        resp = dev_client.get("/not-found", headers={"X-Request-ID": "test-req-456"})
        body = resp.json()
        assert body["request_id"] == "test-req-456"

    def test_generated_request_id_when_none_provided(self, dev_client):
        resp = dev_client.get("/boom")
        body = resp.json()
        # Should have a generated request_id (12 hex chars)
        assert body["request_id"] is not None
        assert len(body["request_id"]) == 12
