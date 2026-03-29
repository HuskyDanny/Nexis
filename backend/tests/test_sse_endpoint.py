"""Integration tests for the SSE endpoint in thinking_auto.py."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from src.services.session_events import registry, SSEEvent


@pytest.mark.asyncio
async def test_sse_streams_from_queue():
    """Live session: events flow from queue to SSE client."""
    dummy_task = asyncio.ensure_future(asyncio.sleep(100))
    entry = registry.create("live-test", dummy_task)

    # Pre-load events into queue
    await entry.queue.put(
        SSEEvent(
            event="node_start",
            data={"id": "n1", "layer": 1, "type": "effect"},
            id="l:1:n:0",
        )
    )
    await entry.queue.put(
        SSEEvent(
            event="session_complete",
            data={"status": "complete"},
            id="session:complete",
        )
    )

    from src.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", "/api/thinking/live-test/events") as resp:
            assert resp.status_code == 200
            text = ""
            async for chunk in resp.aiter_text():
                text += chunk
                if "session_complete" in text:
                    break
            assert "node_start" in text
            assert "session_complete" in text

    # Cleanup
    registry.remove("live-test")
    dummy_task.cancel()


@pytest.mark.asyncio
async def test_sse_replay_from_db():
    """Completed session: replays nodes from MongoDB."""
    fake_session = {
        "id": "replay-test",
        "status": "complete",
        "nodes": [
            {"id": "n1", "layer": 0, "type": "news", "content": "headline"},
            {"id": "n2", "layer": 1, "type": "effect", "content": "impact"},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }

    mock_col = MagicMock()
    mock_col.find_one = AsyncMock(return_value=fake_session)

    with patch("src.api.thinking_auto.mongodb") as mock_db:
        mock_db.get_collection.return_value = mock_col

        from src.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream("GET", "/api/thinking/replay-test/events") as resp:
                assert resp.status_code == 200
                text = ""
                async for chunk in resp.aiter_text():
                    text += chunk
                    if "session_complete" in text:
                        break

                # Should contain node_start and node_complete for each node
                assert text.count("node_start") == 2
                assert text.count("node_complete") == 2
                # Should contain edges
                assert "edges" in text
                # Should end with session_complete
                assert "session_complete" in text
                # Replay flag
                assert "replay" in text


@pytest.mark.asyncio
async def test_sse_replay_not_found():
    """Unknown session returns error event."""
    mock_col = MagicMock()
    mock_col.find_one = AsyncMock(return_value=None)

    with patch("src.api.thinking_auto.mongodb") as mock_db:
        mock_db.get_collection.return_value = mock_col

        from src.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream("GET", "/api/thinking/nonexistent/events") as resp:
                assert resp.status_code == 200
                text = ""
                async for chunk in resp.aiter_text():
                    text += chunk
                assert "error" in text
                assert "Session not found" in text


@pytest.mark.asyncio
async def test_sse_error_event_terminates_stream():
    """Error events from the pipeline terminate the SSE stream."""
    dummy_task = asyncio.ensure_future(asyncio.sleep(100))
    entry = registry.create("error-test", dummy_task)

    await entry.queue.put(
        SSEEvent(event="error", data={"error": "something broke"}, id="session:error")
    )

    from src.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", "/api/thinking/error-test/events") as resp:
            text = ""
            async for chunk in resp.aiter_text():
                text += chunk
                if "error" in text:
                    break
            assert "something broke" in text

    registry.remove("error-test")
    dummy_task.cancel()
