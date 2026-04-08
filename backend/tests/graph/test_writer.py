"""Tests for GraphWriter async write pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.graph.fakes import FakeGraphStore
from src.graph.writer import GraphWriter


@pytest.fixture
def store() -> FakeGraphStore:
    return FakeGraphStore()


@pytest.fixture
def writer(store: FakeGraphStore) -> GraphWriter:
    return GraphWriter(store, group_id="test")


class TestNewsIngestion:
    """News article ingestion via GraphWriter."""

    async def test_ingest_single_article(
        self, writer: GraphWriter, store: FakeGraphStore
    ) -> None:
        await writer.ingest_news_article(
            title="Fed holds rates steady",
            summary="The Federal Reserve kept rates at 5.25%",
            source="reuters",
        )
        assert len(store.episodes) == 1
        assert store.episodes[0]["source_description"] == "news_reuters"

    async def test_ingest_article_with_timestamp(
        self, writer: GraphWriter, store: FakeGraphStore
    ) -> None:
        pub_time = datetime(2026, 4, 7, 14, 0, tzinfo=timezone.utc)
        await writer.ingest_news_article(
            title="Rate decision",
            summary="Details",
            published_at=pub_time,
        )
        assert "2026-04-07" in store.episodes[0]["reference_time"]

    async def test_ingest_batch(
        self, writer: GraphWriter, store: FakeGraphStore
    ) -> None:
        articles = [
            {"title": "Article 1", "summary": "Summary 1", "source": "perigon"},
            {"title": "Article 2", "summary": "Summary 2", "source": "newsapi"},
            {"title": "Article 3", "summary": "Summary 3"},
        ]
        await writer.ingest_news_batch(articles)
        assert len(store.episodes) == 3

    async def test_ingest_batch_uses_canonical_title(
        self, writer: GraphWriter, store: FakeGraphStore
    ) -> None:
        articles = [{"canonical_title": "Canonical Title", "description": "Desc"}]
        await writer.ingest_news_batch(articles)
        assert store.episodes[0]["name"] == "Canonical Title"


class TestThinkingIngestion:
    """Thinking pipeline output ingestion via GraphWriter."""

    async def test_ingest_effect_node(
        self, writer: GraphWriter, store: FakeGraphStore
    ) -> None:
        await writer.ingest_thinking_node(
            content="Supply chain disruption in semiconductor sector",
            reasoning="China tariffs increase costs for chip manufacturers",
            node_type="effect",
            layer=1,
            session_id="abc123",
        )
        assert len(store.episodes) == 1
        ep = store.episodes[0]
        assert "thinking_effect_layer1" in ep["source_description"]
        assert "abc123" in ep["source_description"]

    async def test_ingest_opportunity_node(
        self, writer: GraphWriter, store: FakeGraphStore
    ) -> None:
        await writer.ingest_thinking_node(
            content="NVDA undervalued due to overcorrection",
            node_type="opportunity",
            layer=2,
        )
        assert len(store.episodes) == 1
        assert "thinking_opportunity_layer2" in store.episodes[0]["source_description"]

    async def test_ingest_thinking_layer(
        self, writer: GraphWriter, store: FakeGraphStore
    ) -> None:
        nodes = [
            {"content": "Effect 1", "reasoning": "Because X", "type": "effect"},
            {"content": "Effect 2", "reasoning": "Because Y", "type": "effect"},
            {"content": "Opportunity 1", "type": "opportunity"},
        ]
        await writer.ingest_thinking_layer("session_abc", layer=1, nodes=nodes)
        assert len(store.episodes) == 3


class TestErrorHandling:
    """GraphWriter must not propagate errors."""

    async def test_failed_episode_does_not_raise(self) -> None:
        """If the store raises, writer logs but doesn't propagate."""

        class FailingStore(FakeGraphStore):
            async def add_episode(self, *args, **kwargs) -> str:
                raise ConnectionError("Neo4j down")

        writer = GraphWriter(FailingStore(), group_id="test")
        # Should not raise
        await writer.ingest_news_article(title="Test", summary="Test")

    async def test_batch_continues_after_failure(self) -> None:
        """One failing article in a batch doesn't stop the rest."""
        call_count = 0

        class PartialFailStore(FakeGraphStore):
            async def add_episode(self, *args, **kwargs) -> str:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise ConnectionError("Transient failure")
                return await super().add_episode(*args, **kwargs)

        store = PartialFailStore()
        writer = GraphWriter(store, group_id="test")
        articles = [
            {"title": f"Article {i}", "summary": f"Summary {i}"} for i in range(3)
        ]
        await writer.ingest_news_batch(articles)
        # 2 of 3 should succeed (article 2 fails)
        assert len(store.episodes) == 2
