"""Tests for run_layer_streaming() — streaming thinker + batch matcher/controller."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.session_events import SessionRegistry
from src.services.thinking_service import LayerResult, run_layer_streaming


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_THINKER_JSON = json.dumps(
    {
        "effects": [
            {
                "content": "Rising rates pressure tech valuations",
                "reasoning": "Higher discount rates reduce NPV of future earnings",
                "confidence": 75,
                "parent_ids": ["seed-1"],
                "sector": "technology",
                "fetched_news_ids": [],
                "information_gaps": [],
            }
        ]
    }
)


def _make_chunk(text: str):
    """Build a fake LiteLLM streaming chunk."""
    delta = MagicMock()
    delta.content = text
    choice = MagicMock()
    choice.delta = delta
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


async def _fake_acompletion(**kwargs):
    """Return an async generator of fake chunks that spell out FAKE_THINKER_JSON."""
    # Split into small pieces to exercise the incremental parser
    text = FAKE_THINKER_JSON
    chunk_size = 30

    async def _gen():
        for i in range(0, len(text), chunk_size):
            yield _make_chunk(text[i : i + chunk_size])

    return _gen()


# Matcher returns empty matches, controller returns stop
def _matcher_result(*args, **kwargs):
    return [], [], 0


def _controller_result(*args, **kwargs):
    return {"continue": False, "reasoning": "stop", "summary": "done"}, 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PARENT_NODES = [
    {
        "id": "seed-1",
        "layer": 0,
        "type": "seed",
        "content": "Fed raises rates by 25bp",
        "reasoning": "",
        "confidence": 100,
        "sources": [],
        "parents": [],
        "selected": True,
        "metadata": {"sector": "macro"},
    }
]


@pytest.fixture()
def registry():
    return SessionRegistry()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_layer_emits_expected_events(registry):
    """Full happy-path: thinker streams, matcher/controller run batch."""
    # Register session with a dummy task
    dummy_task = asyncio.ensure_future(asyncio.sleep(999))
    entry = registry.create("test-session", dummy_task)

    try:
        with (
            patch(
                "src.services.thinking_service.litellm_acompletion",
                side_effect=_fake_acompletion,
            ),
            patch(
                "src.services.thinking_service.get_litellm_params",
                return_value={
                    "model": "test",
                    "api_key": "fake",
                    "api_base": "http://fake",
                    "temperature": 0.3,
                },
            ),
            patch(
                "src.services.thinking_service._call_with_retry",
                new_callable=AsyncMock,
            ) as mock_retry,
        ):
            # First call = matcher, second call = controller
            mock_retry.side_effect = [_matcher_result(), _controller_result()]

            result = await run_layer_streaming(
                session_id="test-session",
                registry=registry,
                chain_summary="",
                parent_nodes=PARENT_NODES,
                news_pool=[],
                value_pool=[],
                layer=1,
                max_depth=3,
            )

        # --- Verify result ---
        assert isinstance(result, LayerResult)
        assert len(result.effect_nodes) >= 1
        assert (
            result.effect_nodes[0]["content"] == "Rising rates pressure tech valuations"
        )
        assert result.controller_decision["continue"] is False

        # --- Drain queue and check event types ---
        events = []
        while not entry.queue.empty():
            events.append(entry.queue.get_nowait())

        event_types = [e.event for e in events]

        # Must contain key event types
        assert (
            "node_start" in event_types or "node_complete" in event_types
        ), f"Expected node events, got: {event_types}"
        assert "edges" in event_types, f"Expected edges event, got: {event_types}"
        assert (
            "layer_complete" in event_types
        ), f"Expected layer_complete, got: {event_types}"

        # layer_complete should be the last event
        assert event_types[-1] == "layer_complete"

        # layer_complete data should contain controller decision
        lc_event = events[-1]
        assert lc_event.data["layer"] == 1
        assert lc_event.data["controller"]["continue"] is False
    finally:
        dummy_task.cancel()
        try:
            await dummy_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_streaming_layer_unregistered_session(registry):
    """Calling with a session_id not in registry returns empty result."""
    result = await run_layer_streaming(
        session_id="nonexistent",
        registry=registry,
        chain_summary="",
        parent_nodes=PARENT_NODES,
        news_pool=[],
        value_pool=[],
        layer=1,
        max_depth=3,
    )
    assert isinstance(result, LayerResult)
    assert result.controller_decision["continue"] is False


@pytest.mark.asyncio
async def test_streaming_layer_no_parents(registry):
    """No parent nodes -> empty result with layer_complete event."""
    dummy_task = asyncio.ensure_future(asyncio.sleep(999))
    entry = registry.create("test-no-parents", dummy_task)

    try:
        result = await run_layer_streaming(
            session_id="test-no-parents",
            registry=registry,
            chain_summary="",
            parent_nodes=[],
            news_pool=[],
            value_pool=[],
            layer=1,
            max_depth=3,
        )

        assert result.controller_decision["continue"] is False
        events = []
        while not entry.queue.empty():
            events.append(entry.queue.get_nowait())
        assert any(e.event == "layer_complete" for e in events)
    finally:
        dummy_task.cancel()
        try:
            await dummy_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_streaming_layer_error_pushes_event(registry):
    """LiteLLM failure pushes an error event and returns empty result."""
    dummy_task = asyncio.ensure_future(asyncio.sleep(999))
    entry = registry.create("test-error", dummy_task)

    try:
        with patch(
            "src.services.thinking_service.litellm_acompletion",
            side_effect=RuntimeError("LLM down"),
        ):
            result = await run_layer_streaming(
                session_id="test-error",
                registry=registry,
                chain_summary="",
                parent_nodes=PARENT_NODES,
                news_pool=[],
                value_pool=[],
                layer=1,
                max_depth=3,
            )

        assert result.controller_decision["continue"] is False
        events = []
        while not entry.queue.empty():
            events.append(entry.queue.get_nowait())
        assert any(e.event == "error" for e in events)
    finally:
        dummy_task.cancel()
        try:
            await dummy_task
        except asyncio.CancelledError:
            pass
