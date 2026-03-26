"""Tests that fakes comply with protocols."""


from src.rag.fakes import (
    FakeEmbedding,
    FakeSparseEncoder,
    FakeVectorStore,
    FakeNodeRepo,
)


class TestFakeEmbedding:
    async def test_embed_returns_correct_dim(self):
        emb = FakeEmbedding(dim=1024)
        result = await emb.embed("test text")
        assert len(result) == 1024
        assert all(isinstance(v, float) for v in result)

    async def test_embed_deterministic(self):
        emb = FakeEmbedding(dim=1024)
        r1 = await emb.embed("same text")
        r2 = await emb.embed("same text")
        assert r1 == r2

    async def test_embed_different_texts(self):
        emb = FakeEmbedding(dim=1024)
        r1 = await emb.embed("text one")
        r2 = await emb.embed("text two")
        assert r1 != r2

    async def test_embed_batch(self):
        emb = FakeEmbedding(dim=1024)
        results = await emb.embed_batch(["a", "b", "c"])
        assert len(results) == 3
        assert all(len(v) == 1024 for v in results)


class TestFakeSparseEncoder:
    def test_encode_returns_indices_values(self):
        enc = FakeSparseEncoder()
        indices, values = enc.encode("hello world test")
        assert len(indices) == len(values)
        assert len(indices) == 3
        assert all(isinstance(i, int) for i in indices)
        assert all(isinstance(v, float) for v in values)

    def test_encode_empty_string(self):
        enc = FakeSparseEncoder()
        indices, values = enc.encode("")
        assert indices == []
        assert values == []


class TestFakeVectorStore:
    async def test_upsert_and_query(self):
        store = FakeVectorStore()
        await store.upsert(
            "nodes",
            [
                {
                    "id": "n1",
                    "vector": {"dense": [1.0, 0.0], "sparse": ([0], [1.0])},
                    "payload": {"node_type": "effect", "confidence": 80},
                },
            ],
        )
        results = await store.query(
            "nodes",
            dense=[1.0, 0.0],
            sparse=([0], [1.0]),
            filters={},
            limit=10,
        )
        assert len(results) == 1
        assert results[0]["id"] == "n1"

    async def test_delete(self):
        store = FakeVectorStore()
        await store.upsert(
            "nodes",
            [
                {
                    "id": "n1",
                    "vector": {"dense": [1.0], "sparse": ([0], [1.0])},
                    "payload": {},
                },
            ],
        )
        await store.delete("nodes", ["n1"])
        results = await store.query(
            "nodes", dense=[1.0], sparse=([0], [1.0]), filters={}, limit=10
        )
        assert len(results) == 0

    async def test_filter_by_payload(self):
        store = FakeVectorStore()
        await store.upsert(
            "nodes",
            [
                {
                    "id": "n1",
                    "vector": {"dense": [1.0], "sparse": ([0], [1.0])},
                    "payload": {"node_type": "effect"},
                },
                {
                    "id": "n2",
                    "vector": {"dense": [1.0], "sparse": ([0], [1.0])},
                    "payload": {"node_type": "news"},
                },
            ],
        )
        results = await store.query(
            "nodes",
            dense=[1.0],
            sparse=([0], [1.0]),
            filters={"node_type": ["effect"]},
            limit=10,
        )
        assert len(results) == 1
        assert results[0]["id"] == "n1"


class TestFakeNodeRepo:
    async def test_insert_and_get(self):
        repo = FakeNodeRepo()
        doc = {"id": "n1", "content": "test", "indexed": True}
        await repo.insert(doc)
        result = await repo.get("n1")
        assert result["content"] == "test"

    async def test_find_unindexed(self):
        repo = FakeNodeRepo()
        await repo.insert({"id": "n1", "indexed": True})
        await repo.insert({"id": "n2", "indexed": False})
        unindexed = await repo.find_unindexed()
        assert len(unindexed) == 1
        assert unindexed[0]["id"] == "n2"

    async def test_delete_older_than(self):
        from datetime import datetime, timezone, timedelta

        repo = FakeNodeRepo()
        old = datetime.now(timezone.utc) - timedelta(days=100)
        new = datetime.now(timezone.utc) - timedelta(days=10)
        await repo.insert({"id": "old", "created_at": old, "indexed": True})
        await repo.insert({"id": "new", "created_at": new, "indexed": True})
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        deleted = await repo.delete_older_than(cutoff)
        assert deleted == 1
        assert await repo.get("new") is not None
        assert await repo.get("old") is None

    async def test_mark_indexed(self):
        repo = FakeNodeRepo()
        await repo.insert({"id": "n1", "indexed": False})
        await repo.mark_indexed("n1", True)
        doc = await repo.get("n1")
        assert doc["indexed"] is True
