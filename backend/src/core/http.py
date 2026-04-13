"""Shared resilient HTTP client with connection pooling and retry logic."""

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return the module-level singleton HTTP client, creating it on first use."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
            timeout=httpx.Timeout(15.0, connect=5.0),
        )
    return _client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
    reraise=True,
)
async def resilient_get(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
) -> httpx.Response:
    """GET with automatic retry on transient connection failures."""
    client = _get_client()
    return await client.get(url, params=params, headers=headers)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
    reraise=True,
)
async def resilient_post(
    url: str,
    *,
    json: dict | None = None,
    data: dict | None = None,
    headers: dict | None = None,
) -> httpx.Response:
    """POST with automatic retry on transient connection failures."""
    client = _get_client()
    return await client.post(url, json=json, data=data, headers=headers)


async def close_http_client() -> None:
    """Close the shared HTTP client. Call during application shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
