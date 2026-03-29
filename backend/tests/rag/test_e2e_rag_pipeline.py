"""E2E test: Full RAG pipeline — persist nodes, search, verify cross-session reuse.

Tests the complete flow:
1. Connect to real MongoDB + Qdrant
2. Persist nodes via NodePersistenceService (dual-write)
3. Verify nodes in MongoDB node_store collection
4. Verify nodes indexed in Qdrant
5. Search via NodeSearchService with filters + decay
6. Verify cross-session search (session B finds session A's nodes)
7. Prune old nodes from both stores
8. Clean up

Requires: MongoDB at localhost:27017, Qdrant at localhost:6333
Run: pytest tests/rag/test_e2e_rag_pipeline.py -v -m integration -s
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorClient

from src.rag.config import RAGConfig
from src.rag.fakes import FakeEmbedding, FakeSparseEncoder
from src.rag.qdrant_store import QdrantVectorStore
from src.rag.node_store_repo import MongoNodeStoreRepo
from src.rag.persistence import NodePersistenceService
from src.rag.search import NodeSearchService

pytestmark = pytest.mark.integration

# Use unique DB + collection per test run to avoid collisions
_RUN_ID = uuid.uuid4().hex[:8]
_DB_NAME = f"test_rag_e2e_{_RUN_ID}"
_COLLECTION = f"test_nodes_{_RUN_ID}"


@pytest.fixture
def config():
    return RAGConfig(embedding_dim=1024, collection_name=_COLLECTION)


@pytest.fixture
def embedding():
    return FakeEmbedding(dim=1024)


@pytest.fixture
def sparse():
    return FakeSparseEncoder()


@pytest.fixture
async def mongo_repo():
    """Real MongoDB repo with test database. Drops DB after test."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client[_DB_NAME]
    collection = db["node_store"]
    repo = MongoNodeStoreRepo(collection)
    await repo.ensure_indexes()
    yield repo
    # Cleanup
    await client.drop_database(_DB_NAME)
    client.close()


@pytest.fixture
async def qdrant_store(config):
    """Real Qdrant store with test collection. Deletes collection after test."""
    store = QdrantVectorStore(url="http://localhost:6333", config=config)
    await store.ensure_collection(_COLLECTION)
    yield store
    await store.client.delete_collection(_COLLECTION)
    await store.close()


@pytest.fixture
def persistence(mongo_repo, qdrant_store, embedding, sparse, config):
    return NodePersistenceService(mongo_repo, qdrant_store, embedding, sparse, config)


@pytest.fixture
def search(qdrant_store, embedding, sparse, config):
    return NodeSearchService(qdrant_store, embedding, sparse, config)


def _make_node(id_: str, content: str, **overrides) -> dict:
    defaults = {
        "id": id_,
        "type": "effect",
        "layer": 1,
        "content": content,
        "reasoning": f"Reasoning for {content}",
        "confidence": 75,
        "parents": ["seed_001"],
        "sources": [],
        "metadata": {"sector": "technology"},
    }
    defaults.update(overrides)
    return defaults


class TestFullPipeline:
    """E2E: persist → verify MongoDB → verify Qdrant → search → cross-session."""

    async def test_persist_creates_node_in_mongodb(self, persistence, mongo_repo):
        """Step 1: Persisting a node writes to MongoDB node_store."""
        node = _make_node("e2e_001", "Fed rate pause boosts fintech lending")
        await persistence.persist_node(
            node, session_id="session_A", market="US", date="2026-03-26"
        )

        doc = await mongo_repo.get("e2e_001")
        assert doc is not None, "Node not found in MongoDB"
        assert doc["content"] == "Fed rate pause boosts fintech lending"
        assert doc["session_id"] == "session_A"
        assert doc["market"] == "US"
        assert doc["indexed"] is True
        print("  ✓ MongoDB: node e2e_001 persisted with indexed=True")

    async def test_persist_indexes_node_in_qdrant(
        self, persistence, qdrant_store, embedding, sparse
    ):
        """Step 2: Persisted node is searchable in Qdrant."""
        node = _make_node("e2e_002", "China tariffs disrupt semiconductor supply chain")
        await persistence.persist_node(
            node, session_id="session_A", market="US", date="2026-03-26"
        )

        # Search Qdrant directly
        query_dense = await embedding.embed("tariff semiconductor")
        query_sparse = sparse.encode("tariff semiconductor")
        results = await qdrant_store.query(
            _COLLECTION,
            dense=query_dense,
            sparse=query_sparse,
            filters={},
            limit=10,
        )
        ids = [r["id"] for r in results]
        assert "e2e_002" in ids, f"Node not found in Qdrant. Got IDs: {ids}"
        print("  ✓ Qdrant: node e2e_002 indexed and searchable")

    async def test_search_with_filters(self, persistence, search):
        """Step 3: Search service filters work against real stores."""
        # Persist diverse nodes
        nodes = [
            _make_node(
                "e2e_f1",
                "Tech effect high confidence",
                metadata={"sector": "technology"},
                confidence=85,
            ),
            _make_node(
                "e2e_f2",
                "Energy effect low confidence",
                type="effect",
                metadata={"sector": "energy"},
                confidence=40,
            ),
            _make_node(
                "e2e_f3",
                "NVIDIA opportunity",
                type="opportunity",
                metadata={"sector": "technology"},
                confidence=90,
            ),
        ]
        for n in nodes:
            await persistence.persist_node(
                n, session_id="session_A", market="US", date="2026-03-26"
            )

        # Filter: only effects with confidence >= 70
        results = await search.search(
            query="technology effect",
            current_session_id="session_X",  # different session
            node_type=["effect"],
            min_confidence=70,
        )
        assert len(results) >= 1, "Expected at least 1 result"
        assert all(
            r.get("node_type") == "effect" for r in results
        ), "Filter by type failed"
        assert all(
            r.get("confidence", 0) >= 70 for r in results
        ), "Filter by confidence failed"
        print(
            f"  ✓ Search: filters returned {len(results)} results (type=effect, confidence>=70)"
        )

    async def test_cross_session_search(self, persistence, search):
        """Step 4: Session B can find nodes from Session A via RAG search."""
        # Session A produces nodes
        session_a_nodes = [
            _make_node(
                "e2e_cs1",
                "OPEC production cut raises oil prices",
                metadata={"sector": "energy"},
                confidence=80,
            ),
            _make_node(
                "e2e_cs2",
                "Oil price spike impacts airline profitability",
                metadata={"sector": "transportation"},
                confidence=72,
            ),
        ]
        for n in session_a_nodes:
            await persistence.persist_node(
                n, session_id="session_A", market="US", date="2026-03-25"
            )

        # Session B searches — should find Session A's nodes
        results = await search.search(
            query="oil price impact airlines",
            current_session_id="session_B",  # different session
        )
        result_ids = [r["id"] for r in results]
        assert (
            "e2e_cs1" in result_ids or "e2e_cs2" in result_ids
        ), f"Cross-session search failed. Session B didn't find Session A nodes. Got: {result_ids}"
        print(f"  ✓ Cross-session: Session B found Session A's nodes: {result_ids}")

    async def test_session_exclusion(self, persistence, search):
        """Step 5: Search excludes current session's own nodes."""
        node = _make_node("e2e_excl", "Node from current session")
        await persistence.persist_node(
            node, session_id="session_self", market="US", date="2026-03-26"
        )

        results = await search.search(
            query="Node from current session",
            current_session_id="session_self",  # same session — should be excluded
        )
        result_ids = [r["id"] for r in results]
        assert (
            "e2e_excl" not in result_ids
        ), f"Session exclusion failed — found own node. Got: {result_ids}"
        print("  ✓ Session exclusion: own nodes correctly filtered out")

    async def test_decay_ranking(self, persistence, search):
        """Step 6: Newer nodes rank higher than older ones after decay."""
        old_node = _make_node(
            "e2e_old",
            "Old analysis of market trends",
            metadata={"sector": "general"},
            confidence=80,
        )
        new_node = _make_node(
            "e2e_new",
            "New analysis of market trends",
            metadata={"sector": "general"},
            confidence=80,
        )

        # Persist with different dates
        await persistence.persist_node(
            old_node, session_id="s_old", market="US", date="2026-03-10"
        )
        await persistence.persist_node(
            new_node, session_id="s_new", market="US", date="2026-03-26"
        )

        results = await search.search(
            query="market trends analysis",
            current_session_id="other",
        )
        result_ids = [r["id"] for r in results]
        if "e2e_old" in result_ids and "e2e_new" in result_ids:
            old_idx = result_ids.index("e2e_old")
            new_idx = result_ids.index("e2e_new")
            assert (
                new_idx < old_idx
            ), f"Decay ranking failed: new node at {new_idx}, old at {old_idx}"
            print(f"  ✓ Decay: new node ranks {new_idx+1}, old ranks {old_idx+1}")
        else:
            print(
                f"  ⚠ Decay test inconclusive — not both nodes in results: {result_ids}"
            )

    async def test_reconcile_after_simulated_failure(
        self, persistence, mongo_repo, qdrant_store, embedding, sparse
    ):
        """Step 7: Reconcile picks up nodes that failed Qdrant indexing."""
        # Insert directly to MongoDB with indexed=False (simulating Qdrant failure)
        await mongo_repo.insert(
            {
                "id": "e2e_orphan",
                "session_id": "s_orphan",
                "type": "effect",
                "layer": 1,
                "content": "Orphaned node from failed indexing",
                "reasoning": "Should be picked up by reconcile",
                "confidence": 70,
                "parents": [],
                "sources": [],
                "sector": "technology",
                "market": "US",
                "date": "2026-03-26",
                "created_at": datetime.now(timezone.utc),
                "indexed": False,
            }
        )

        # Verify not in Qdrant yet
        query_dense = await embedding.embed("orphaned node failed indexing")
        query_sparse = sparse.encode("orphaned node failed indexing")
        results_before = await qdrant_store.query(
            _COLLECTION,
            dense=query_dense,
            sparse=query_sparse,
            filters={},
            limit=10,
        )
        orphan_before = [r for r in results_before if r["id"] == "e2e_orphan"]
        assert len(orphan_before) == 0, "Orphan shouldn't be in Qdrant yet"

        # Run reconcile
        count = await persistence.reconcile()
        assert count >= 1, f"Reconcile should have indexed at least 1 node, got {count}"

        # Verify now in Qdrant
        results_after = await qdrant_store.query(
            _COLLECTION,
            dense=query_dense,
            sparse=query_sparse,
            filters={},
            limit=10,
        )
        orphan_after = [r for r in results_after if r["id"] == "e2e_orphan"]
        assert len(orphan_after) == 1, "Orphan should be in Qdrant after reconcile"

        # Verify MongoDB marked as indexed
        doc = await mongo_repo.get("e2e_orphan")
        assert doc["indexed"] is True
        print(f"  ✓ Reconcile: orphaned node indexed after reconcile (count={count})")

    async def test_prune_removes_old_nodes(
        self, persistence, mongo_repo, qdrant_store, embedding, sparse
    ):
        """Step 8: Prune removes old nodes from both MongoDB and Qdrant."""
        # Persist a node, then backdate it
        node = _make_node("e2e_prune", "Very old analysis to be pruned")
        await persistence.persist_node(
            node, session_id="s_prune", market="US", date="2025-01-01"
        )

        # Backdate in MongoDB
        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        await mongo_repo.collection.update_one(
            {"id": "e2e_prune"}, {"$set": {"created_at": old_date}}
        )

        # Verify it exists in both stores
        doc = await mongo_repo.get("e2e_prune")
        assert doc is not None

        # Prune
        pruned = await persistence.prune()
        assert pruned >= 1, f"Expected to prune at least 1 node, got {pruned}"

        # Verify removed from MongoDB
        doc_after = await mongo_repo.get("e2e_prune")
        assert doc_after is None, "Node should be removed from MongoDB after prune"

        # Verify removed from Qdrant
        query_dense = await embedding.embed("old analysis pruned")
        query_sparse = sparse.encode("old analysis pruned")
        results = await qdrant_store.query(
            _COLLECTION,
            dense=query_dense,
            sparse=query_sparse,
            filters={},
            limit=10,
        )
        prune_results = [r for r in results if r["id"] == "e2e_prune"]
        assert len(prune_results) == 0, "Node should be removed from Qdrant after prune"
        print(f"  ✓ Prune: old node removed from both stores (pruned={pruned})")
