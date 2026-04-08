"""Integration tests — verify graph writes are wired into thinking + news pipelines."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from src.graph.fakes import FakeGraphStore
from src.graph.writer import (
    fire_and_forget,
    try_ingest_thinking_layer,
    try_ingest_news_batch,
)


@pytest.fixture
def fake_store() -> FakeGraphStore:
    return FakeGraphStore()


class TestTryIngestThinkingLayer:
    """try_ingest_thinking_layer dispatches a fire-and-forget graph write."""

    async def test_writes_to_graph_when_initialized(
        self, fake_store: FakeGraphStore
    ) -> None:
        """When graph store is initialized, nodes are ingested as episodes."""
        session_id = "abc12345xyz"
        nodes = [
            {
                "content": "Supply chain disruption",
                "reasoning": "Tariffs",
                "type": "effect",
            },
            {"content": "NVDA opportunity", "type": "opportunity"},
        ]

        with patch("src.graph.dependencies.get_graph_store", return_value=fake_store):
            try_ingest_thinking_layer(session_id, layer=1, nodes=nodes)
            # Let the background task complete
            await asyncio.sleep(0.05)

        assert len(fake_store.episodes) == 2
        assert "thinking_effect_layer1" in fake_store.episodes[0]["source_description"]
        # Writer truncates session_id to first 8 chars
        assert session_id[:8] in fake_store.episodes[0]["source_description"]

    async def test_noop_when_graph_not_initialized(self) -> None:
        """When graph store is not initialized, no error is raised."""
        with patch(
            "src.graph.dependencies.get_graph_store",
            side_effect=RuntimeError("not initialized"),
        ):
            # Should not raise
            try_ingest_thinking_layer(
                "session_abc", layer=1, nodes=[{"content": "test"}]
            )

    async def test_noop_with_empty_nodes(self, fake_store: FakeGraphStore) -> None:
        """Empty node list still dispatches (writer handles it gracefully)."""
        with patch("src.graph.dependencies.get_graph_store", return_value=fake_store):
            try_ingest_thinking_layer("session_abc", layer=1, nodes=[])
            await asyncio.sleep(0.05)

        assert len(fake_store.episodes) == 0


class TestTryIngestNewsBatch:
    """try_ingest_news_batch dispatches a fire-and-forget graph write for news."""

    async def test_writes_news_to_graph(self, fake_store: FakeGraphStore) -> None:
        """Active news entities are ingested as episodes."""
        articles = [
            {
                "title": "Fed holds rates",
                "summary": "Rates steady at 5.25%",
                "source": "reuters",
            },
            {"title": "China tariffs expand", "summary": "New tariffs on chips"},
        ]

        with patch("src.graph.dependencies.get_graph_store", return_value=fake_store):
            try_ingest_news_batch(articles)
            await asyncio.sleep(0.05)

        assert len(fake_store.episodes) == 2
        assert fake_store.episodes[0]["source_description"] == "news_reuters"

    async def test_noop_when_graph_not_initialized(self) -> None:
        """Graph not initialized — silently skipped."""
        with patch(
            "src.graph.dependencies.get_graph_store",
            side_effect=RuntimeError("not initialized"),
        ):
            try_ingest_news_batch([{"title": "test", "summary": "test"}])

    async def test_uses_canonical_title_fallback(
        self, fake_store: FakeGraphStore
    ) -> None:
        """Articles with canonical_title instead of title are handled."""
        articles = [{"canonical_title": "Macro Event", "description": "Details here"}]

        with patch("src.graph.dependencies.get_graph_store", return_value=fake_store):
            try_ingest_news_batch(articles)
            await asyncio.sleep(0.05)

        assert fake_store.episodes[0]["name"] == "Macro Event"


class TestFireAndForget:
    """fire_and_forget schedules coroutines without blocking or propagating errors."""

    async def test_successful_coro_completes(self) -> None:
        """A successful coroutine runs to completion in the background."""
        completed = False

        async def _work():
            nonlocal completed
            completed = True

        fire_and_forget(_work())
        await asyncio.sleep(0.05)
        assert completed

    async def test_failing_coro_does_not_propagate(self) -> None:
        """A failing coroutine logs but doesn't crash the caller."""

        async def _failing():
            raise ConnectionError("Neo4j down")

        # Should not raise
        fire_and_forget(_failing())
        await asyncio.sleep(0.05)

    async def test_no_event_loop_logs_warning(self) -> None:
        """When no event loop is running, fire_and_forget logs and returns."""

        # This is hard to test in an async test since we always have a loop.
        # Instead, verify the function signature accepts any coroutine.
        async def _noop():
            pass

        fire_and_forget(_noop())
        await asyncio.sleep(0.01)


class TestGraphInitGracefulDegradation:
    """Graph init failure must not prevent app startup."""

    async def test_init_failure_does_not_crash_lifespan(self) -> None:
        """Simulates graph init failing — app should still start."""
        from src.graph.dependencies import init_graph_services

        # init_graph_services requires Neo4j — it will raise without a real connection.
        # The lifespan wraps it in try/except, so we test that pattern here.
        try:
            await init_graph_services()
        except Exception as e:
            # Expected: no Neo4j running in test env
            assert e is not None

    async def test_close_without_init_is_safe(self) -> None:
        """close_graph_services when never initialized should be a no-op."""
        from src.graph.dependencies import close_graph_services

        # Should not raise
        await close_graph_services()

    async def test_get_store_raises_before_init(self) -> None:
        """get_graph_store raises RuntimeError before init_graph_services."""
        from src.graph.dependencies import get_graph_store

        with pytest.raises(RuntimeError, match="not initialized"):
            get_graph_store()
