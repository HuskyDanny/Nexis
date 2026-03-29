"""Integration tests for QdrantVectorStore with a real Qdrant instance.

Requires: Qdrant running at localhost:6333 (docker compose up qdrant)
Run: pytest tests/rag/test_qdrant_integration.py -v -m integration
"""

import pytest
import uuid

from src.rag.config import RAGConfig
from src.rag.qdrant_store import QdrantVectorStore
from src.rag.fakes import FakeEmbedding, FakeSparseEncoder

pytestmark = pytest.mark.integration


def _unique_collection() -> str:
    """Generate a unique collection name per test run to avoid collisions."""
    return f"test_nodes_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def config():
    return RAGConfig(embedding_dim=1024, hnsw_m=16, hnsw_ef_construct=100)


@pytest.fixture
async def store(config):
    """Real Qdrant store — creates a unique collection, cleans up after test."""
    s = QdrantVectorStore(url="http://localhost:6333", config=config)
    collection = _unique_collection()
    await s.ensure_collection(collection)
    yield s, collection
    # Cleanup: delete the test collection
    await s.client.delete_collection(collection)
    await s.close()


@pytest.fixture
def embedding():
    return FakeEmbedding(dim=1024)


@pytest.fixture
def sparse():
    return FakeSparseEncoder()


async def _make_point_async(
    id_: str, text: str, embedding, sparse, **payload_overrides
):
    """Async helper to build a point dict."""
    dense = await embedding.embed(text)
    indices, values = sparse.encode(text)
    payload = {
        "node_type": "effect",
        "sector": "technology",
        "confidence": 75,
        "layer": 1,
        "market": "US",
        "date": "2026-03-25T00:00:00Z",
        "session_id": "s1",
        "content": text,
        "reasoning": "test reasoning",
    }
    payload.update(payload_overrides)
    return {
        "id": id_,
        "vector": {"dense": dense, "sparse": (indices, values)},
        "payload": payload,
    }


class TestQdrantConnection:
    async def test_ensure_collection_creates_collection(self, store):
        s, collection = store
        collections = await s.client.get_collections()
        names = [c.name for c in collections.collections]
        assert collection in names

    async def test_ensure_collection_idempotent(self, store):
        """Calling ensure_collection twice doesn't error."""
        s, collection = store
        await s.ensure_collection(collection)  # second call
        collections = await s.client.get_collections()
        names = [c.name for c in collections.collections]
        assert collection in names


class TestUpsertAndQuery:
    async def test_upsert_and_retrieve(self, store, embedding, sparse):
        s, collection = store
        point = await _make_point_async(
            "n1", "Fed rate pause boosts fintech", embedding, sparse
        )
        await s.upsert(collection, [point])

        # Query with the same vector
        results = await s.query(
            collection,
            dense=point["vector"]["dense"],
            sparse=point["vector"]["sparse"],
            filters={},
            limit=10,
        )
        assert len(results) >= 1
        assert results[0]["id"] == "n1"
        assert results[0]["content"] == "Fed rate pause boosts fintech"

    async def test_upsert_multiple_points(self, store, embedding, sparse):
        s, collection = store
        points = [
            await _make_point_async(f"n{i}", f"test content {i}", embedding, sparse)
            for i in range(5)
        ]
        await s.upsert(collection, points)

        results = await s.query(
            collection,
            dense=points[0]["vector"]["dense"],
            sparse=points[0]["vector"]["sparse"],
            filters={},
            limit=10,
        )
        assert len(results) == 5

    async def test_write_then_search_immediate(self, store, embedding, sparse):
        """Verify no eventual consistency lag — node searchable immediately after upsert."""
        s, collection = store
        point = await _make_point_async(
            "immediate", "tariff semiconductor supply chain", embedding, sparse
        )
        await s.upsert(collection, [point])

        # Query immediately — no sleep
        results = await s.query(
            collection,
            dense=point["vector"]["dense"],
            sparse=point["vector"]["sparse"],
            filters={},
            limit=10,
        )
        assert any(r["id"] == "immediate" for r in results)


class TestFilters:
    async def _seed(self, s, collection, embedding, sparse):
        """Seed store with diverse nodes for filter testing."""
        points = [
            await _make_point_async(
                "eff1",
                "Fed rate effect",
                embedding,
                sparse,
                node_type="effect",
                sector="technology",
                confidence=80,
                market="US",
                session_id="s1",
            ),
            await _make_point_async(
                "eff2",
                "Oil demand effect",
                embedding,
                sparse,
                node_type="effect",
                sector="energy",
                confidence=60,
                market="US",
                session_id="s1",
            ),
            await _make_point_async(
                "opp1",
                "NVIDIA opportunity",
                embedding,
                sparse,
                node_type="opportunity",
                sector="technology",
                confidence=90,
                market="CN",
                session_id="s2",
            ),
            await _make_point_async(
                "news1",
                "Fed holds rates",
                embedding,
                sparse,
                node_type="news",
                sector="general",
                confidence=50,
                market="US",
                session_id="s3",
            ),
        ]
        await s.upsert(collection, points)
        return points

    async def test_filter_by_node_type(self, store, embedding, sparse):
        s, collection = store
        points = await self._seed(s, collection, embedding, sparse)
        results = await s.query(
            collection,
            dense=points[0]["vector"]["dense"],
            sparse=points[0]["vector"]["sparse"],
            filters={"node_type": ["effect"]},
            limit=10,
        )
        assert all(r["node_type"] == "effect" for r in results)
        assert len(results) == 2

    async def test_filter_by_min_confidence(self, store, embedding, sparse):
        s, collection = store
        points = await self._seed(s, collection, embedding, sparse)
        results = await s.query(
            collection,
            dense=points[0]["vector"]["dense"],
            sparse=points[0]["vector"]["sparse"],
            filters={"min_confidence": 70},
            limit=10,
        )
        assert all(r["confidence"] >= 70 for r in results)

    async def test_filter_by_market(self, store, embedding, sparse):
        s, collection = store
        points = await self._seed(s, collection, embedding, sparse)
        results = await s.query(
            collection,
            dense=points[0]["vector"]["dense"],
            sparse=points[0]["vector"]["sparse"],
            filters={"market": "CN"},
            limit=10,
        )
        assert all(r["market"] == "CN" for r in results)
        assert len(results) == 1

    async def test_exclude_session_id(self, store, embedding, sparse):
        s, collection = store
        points = await self._seed(s, collection, embedding, sparse)
        results = await s.query(
            collection,
            dense=points[0]["vector"]["dense"],
            sparse=points[0]["vector"]["sparse"],
            filters={"exclude_session_id": "s1"},
            limit=10,
        )
        assert all(r["session_id"] != "s1" for r in results)
        assert len(results) == 2  # opp1 (s2) + news1 (s3)

    async def test_combined_filters(self, store, embedding, sparse):
        s, collection = store
        points = await self._seed(s, collection, embedding, sparse)
        results = await s.query(
            collection,
            dense=points[0]["vector"]["dense"],
            sparse=points[0]["vector"]["sparse"],
            filters={
                "node_type": ["effect"],
                "min_confidence": 70,
                "exclude_session_id": "s99",
            },
            limit=10,
        )
        # Only eff1 matches: effect, confidence=80, not s99
        assert len(results) == 1
        assert results[0]["id"] == "eff1"


class TestDelete:
    async def test_delete_removes_point(self, store, embedding, sparse):
        s, collection = store
        point = await _make_point_async("del1", "delete test", embedding, sparse)
        await s.upsert(collection, [point])

        # Verify it exists
        results = await s.query(
            collection,
            dense=point["vector"]["dense"],
            sparse=point["vector"]["sparse"],
            filters={},
            limit=10,
        )
        assert any(r["id"] == "del1" for r in results)

        # Delete it
        await s.delete(collection, ["del1"])

        # Verify it's gone
        results = await s.query(
            collection,
            dense=point["vector"]["dense"],
            sparse=point["vector"]["sparse"],
            filters={},
            limit=10,
        )
        assert not any(r["id"] == "del1" for r in results)

    async def test_delete_empty_ids_is_noop(self, store):
        s, collection = store
        await s.delete(collection, [])  # should not raise


class TestHybridSearch:
    async def test_rrf_fusion_returns_scored_results(self, store, embedding, sparse):
        """Verify hybrid search produces RRF-fused scores."""
        s, collection = store
        points = [
            await _make_point_async(
                "h1", "Federal Reserve interest rate decision", embedding, sparse
            ),
            await _make_point_async(
                "h2", "Oil prices surge on OPEC decision", embedding, sparse
            ),
            await _make_point_async(
                "h3", "Fed rate pause boosts fintech lending", embedding, sparse
            ),
        ]
        await s.upsert(collection, points)

        # Query with text related to "Fed rate"
        query_dense = await embedding.embed("Fed rate impact")
        query_sparse = sparse.encode("Fed rate impact")
        results = await s.query(
            collection,
            dense=query_dense,
            sparse=query_sparse,
            filters={},
            limit=10,
        )
        assert len(results) == 3
        # All results should have scores
        assert all(r["score"] > 0 for r in results)
        # Results should be sorted by score descending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
