"""Tests for NodePersistenceService dual-write logic."""

import pytest
from unittest.mock import AsyncMock

from src.rag.persistence import NodePersistenceService


def _make_node(id_: str = "n1", **overrides) -> dict:
    defaults = {
        "id": id_,
        "type": "effect",
        "layer": 1,
        "content": "Fed rate pause impacts fintech",
        "reasoning": "Historical pattern shows rate pauses benefit lenders",
        "confidence": 75,
        "parents": ["news_001"],
        "sources": [],
        "metadata": {"sector": "technology"},
    }
    defaults.update(overrides)
    return defaults


@pytest.fixture
def service(fake_repo, fake_store, fake_embedding, fake_sparse, rag_config):
    return NodePersistenceService(
        node_repo=fake_repo,
        vector_store=fake_store,
        embedder=fake_embedding,
        sparse_encoder=fake_sparse,
        config=rag_config,
    )


class TestPersistNode:
    async def test_writes_to_both_stores(self, service, fake_repo, fake_store):
        await service.persist_node(
            _make_node(), session_id="s1", market="US", date="2026-03-26"
        )
        assert await fake_repo.get("n1") is not None
        assert "n1" in fake_store.points

    async def test_node_store_doc_shape(self, service, fake_repo):
        await service.persist_node(
            _make_node(id_="n2"), session_id="s1", market="US", date="2026-03-26"
        )
        doc = await fake_repo.get("n2")
        assert doc["session_id"] == "s1"
        assert doc["market"] == "US"
        assert doc["date"] == "2026-03-26"
        assert doc["type"] == "effect"
        assert doc["sector"] == "technology"
        assert doc["indexed"] is True

    async def test_vector_store_payload_shape(self, service, fake_store):
        await service.persist_node(
            _make_node(), session_id="s1", market="US", date="2026-03-26"
        )
        point = fake_store.points["n1"]
        payload = point["payload"]
        assert payload["node_type"] == "effect"
        assert payload["confidence"] == 75
        assert payload["session_id"] == "s1"
        assert "dense" in point["vector"]
        assert "sparse" in point["vector"]

    async def test_survives_vector_store_failure(
        self, fake_repo, fake_embedding, fake_sparse, rag_config
    ):
        broken_store = AsyncMock()
        broken_store.upsert = AsyncMock(side_effect=ConnectionError("Qdrant down"))
        svc = NodePersistenceService(
            fake_repo, broken_store, fake_embedding, fake_sparse, rag_config
        )

        await svc.persist_node(
            _make_node(), session_id="s1", market="US", date="2026-03-26"
        )

        doc = await fake_repo.get("n1")
        assert doc is not None
        assert doc["indexed"] is False

    async def test_survives_embedding_failure(
        self, fake_repo, fake_store, fake_sparse, rag_config
    ):
        broken_emb = AsyncMock()
        broken_emb.embed = AsyncMock(side_effect=RuntimeError("API down"))
        svc = NodePersistenceService(
            fake_repo, fake_store, broken_emb, fake_sparse, rag_config
        )

        await svc.persist_node(
            _make_node(), session_id="s1", market="US", date="2026-03-26"
        )

        doc = await fake_repo.get("n1")
        assert doc is not None
        assert doc["indexed"] is False


class TestPersistBatch:
    async def test_batch_persist(self, service, fake_repo, fake_store):
        nodes = [_make_node(id_=f"n{i}") for i in range(5)]
        await service.persist_batch(
            nodes, session_id="s1", market="US", date="2026-03-26"
        )
        assert len(fake_repo.docs) == 5
        assert len(fake_store.points) == 5


class TestReconcile:
    async def test_reconcile_indexes_unindexed_nodes(
        self, service, fake_repo, fake_store
    ):
        await fake_repo.insert(
            {
                "id": "orphan",
                "content": "orphaned node",
                "reasoning": "",
                "type": "effect",
                "indexed": False,
                "session_id": "s1",
                "sector": "energy",
                "confidence": 60,
                "layer": 1,
                "market": "US",
                "date": "2026-03-25",
            }
        )
        assert "orphan" not in fake_store.points

        await service.reconcile()

        assert "orphan" in fake_store.points
        doc = await fake_repo.get("orphan")
        assert doc["indexed"] is True


class TestPrune:
    async def test_prune_removes_old_from_both(self, service, fake_repo, fake_store):
        from datetime import datetime, timezone, timedelta

        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        new_date = datetime.now(timezone.utc) - timedelta(days=10)

        old_node = _make_node(id_="old")
        new_node = _make_node(id_="new")
        await service.persist_node(
            old_node, session_id="s1", market="US", date="2026-01-01"
        )
        await service.persist_node(
            new_node, session_id="s2", market="US", date="2026-03-16"
        )

        fake_repo.docs["old"]["created_at"] = old_date
        fake_repo.docs["new"]["created_at"] = new_date

        pruned = await service.prune()

        assert await fake_repo.get("old") is None
        assert "old" not in fake_store.points
        assert await fake_repo.get("new") is not None
        assert "new" in fake_store.points
        assert pruned == 1
