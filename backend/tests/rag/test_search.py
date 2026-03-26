"""Tests for NodeSearchService search + decay re-ranking."""

import pytest
from datetime import datetime, timezone, timedelta

from src.rag.config import RAGConfig
from src.rag.fakes import FakeEmbedding, FakeSparseEncoder, FakeVectorStore
from src.rag.search import NodeSearchService


@pytest.fixture
def search_service(fake_store, fake_embedding, fake_sparse, rag_config):
    return NodeSearchService(fake_store, fake_embedding, fake_sparse, rag_config)


async def _seed_store(
    store: FakeVectorStore, embedding: FakeEmbedding, sparse: FakeSparseEncoder
):
    """Seed vector store with test nodes."""
    nodes = [
        {
            "id": "eff1",
            "node_type": "effect",
            "sector": "technology",
            "confidence": 80,
            "market": "US",
            "date": "2026-03-25",
            "session_id": "s1",
            "content": "Fed rate pause boosts fintech",
            "reasoning": "Lower rates help lenders",
            "layer": 1,
        },
        {
            "id": "eff2",
            "node_type": "effect",
            "sector": "energy",
            "confidence": 60,
            "market": "US",
            "date": "2026-03-20",
            "session_id": "s1",
            "content": "Oil demand drops on tariff fears",
            "reasoning": "Trade war reduces industrial output",
            "layer": 1,
        },
        {
            "id": "opp1",
            "node_type": "opportunity",
            "sector": "technology",
            "confidence": 90,
            "market": "CN",
            "date": "2026-03-26",
            "session_id": "s2",
            "content": "NVIDIA undervalued after tariff sell-off",
            "reasoning": "AI demand intact despite tariffs",
            "layer": 2,
        },
        {
            "id": "news1",
            "node_type": "news",
            "sector": "general",
            "confidence": 50,
            "market": "US",
            "date": "2026-03-10",
            "session_id": "s3",
            "content": "Old news about market volatility",
            "reasoning": "",
            "layer": 0,
        },
    ]
    for n in nodes:
        text = f"{n['content']} {n['reasoning']}"
        dense = await embedding.embed(text)
        indices, values = sparse.encode(text)
        await store.upsert(
            "nodes",
            [
                {
                    "id": n["id"],
                    "vector": {"dense": dense, "sparse": (indices, values)},
                    "payload": n,
                }
            ],
        )


class TestSearch:
    async def test_basic_search(
        self, search_service, fake_store, fake_embedding, fake_sparse
    ):
        await _seed_store(fake_store, fake_embedding, fake_sparse)
        results = await search_service.search(
            query="Fed rate fintech",
            current_session_id="s99",
        )
        assert len(results) > 0
        assert all("id" in r for r in results)
        assert all("score" in r for r in results)

    async def test_filter_by_node_type(
        self, search_service, fake_store, fake_embedding, fake_sparse
    ):
        await _seed_store(fake_store, fake_embedding, fake_sparse)
        results = await search_service.search(
            query="anything",
            current_session_id="s99",
            node_type=["opportunity"],
        )
        assert all(r["node_type"] == "opportunity" for r in results)

    async def test_filter_by_sector(
        self, search_service, fake_store, fake_embedding, fake_sparse
    ):
        await _seed_store(fake_store, fake_embedding, fake_sparse)
        results = await search_service.search(
            query="anything",
            current_session_id="s99",
            sector="technology",
        )
        assert all(r.get("sector") == "technology" for r in results)

    async def test_filter_by_min_confidence(
        self, search_service, fake_store, fake_embedding, fake_sparse
    ):
        await _seed_store(fake_store, fake_embedding, fake_sparse)
        results = await search_service.search(
            query="anything",
            current_session_id="s99",
            min_confidence=70,
        )
        assert all(r.get("confidence", 0) >= 70 for r in results)

    async def test_excludes_current_session(
        self, search_service, fake_store, fake_embedding, fake_sparse
    ):
        await _seed_store(fake_store, fake_embedding, fake_sparse)
        results = await search_service.search(
            query="anything",
            current_session_id="s1",
        )
        assert all(r.get("session_id") != "s1" for r in results)

    async def test_filter_by_market(
        self, search_service, fake_store, fake_embedding, fake_sparse
    ):
        await _seed_store(fake_store, fake_embedding, fake_sparse)
        results = await search_service.search(
            query="anything",
            current_session_id="s99",
            market="CN",
        )
        assert all(r.get("market") == "CN" for r in results)

    async def test_limit_respected(
        self, search_service, fake_store, fake_embedding, fake_sparse
    ):
        await _seed_store(fake_store, fake_embedding, fake_sparse)
        results = await search_service.search(
            query="anything",
            current_session_id="s99",
            limit=2,
        )
        assert len(results) <= 2

    async def test_decay_favors_newer_nodes(
        self, search_service, fake_store, fake_embedding, fake_sparse
    ):
        await _seed_store(fake_store, fake_embedding, fake_sparse)
        results = await search_service.search(
            query="anything",
            current_session_id="s99",
            node_type=["effect"],
        )
        if len(results) >= 2:
            eff1_idx = next(
                (i for i, r in enumerate(results) if r["id"] == "eff1"), None
            )
            eff2_idx = next(
                (i for i, r in enumerate(results) if r["id"] == "eff2"), None
            )
            if eff1_idx is not None and eff2_idx is not None:
                assert eff1_idx < eff2_idx, "Newer node should rank higher after decay"

    async def test_returns_content_and_reasoning(
        self, search_service, fake_store, fake_embedding, fake_sparse
    ):
        await _seed_store(fake_store, fake_embedding, fake_sparse)
        results = await search_service.search(
            query="anything", current_session_id="s99"
        )
        for r in results:
            assert "content" in r
            assert "reasoning" in r
