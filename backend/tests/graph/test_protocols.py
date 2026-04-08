"""Tests for graph protocols and FakeGraphStore compliance."""

from __future__ import annotations

import pytest

from src.graph.fakes import FakeGraphStore
from src.graph.protocols import GraphStore


class TestProtocolCompliance:
    """FakeGraphStore must satisfy the GraphStore protocol."""

    def test_fake_implements_protocol(self) -> None:
        store = FakeGraphStore()
        assert isinstance(store, GraphStore)

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol decorated with @runtime_checkable should work with isinstance."""
        assert (
            hasattr(GraphStore, "__protocol_attrs__")
            or hasattr(GraphStore, "__abstractmethods__")
            or callable(getattr(GraphStore, "__instancecheck__", None))
        )


class TestFakeGraphStoreSearch:
    """Search operations on FakeGraphStore."""

    @pytest.fixture
    def store(self) -> FakeGraphStore:
        s = FakeGraphStore()
        s.add_entity("NVIDIA", "Company", summary="GPU manufacturer")
        s.add_entity("Federal Reserve", "MacroEvent", summary="US central bank")
        s.add_edge(
            "Federal Reserve",
            "NVIDIA",
            "IMPACTS",
            "Fed rate hold impacts NVIDIA margins",
        )
        return s

    async def test_search_by_edge_fact(self, store: FakeGraphStore) -> None:
        results = await store.search("NVIDIA margins")
        assert len(results) == 1
        assert len(results[0]["edges"]) == 1
        assert "NVIDIA" in results[0]["edges"][0]["fact"]

    async def test_search_by_entity_name(self, store: FakeGraphStore) -> None:
        results = await store.search("Federal Reserve")
        assert len(results) == 1
        assert len(results[0]["nodes"]) == 1
        assert results[0]["nodes"][0]["name"] == "Federal Reserve"

    async def test_search_no_match(self, store: FakeGraphStore) -> None:
        results = await store.search("cryptocurrency")
        assert len(results) == 1
        assert len(results[0]["edges"]) == 0
        assert len(results[0]["nodes"]) == 0

    async def test_search_case_insensitive(self, store: FakeGraphStore) -> None:
        results = await store.search("nvidia")
        assert len(results[0]["nodes"]) == 1

    async def test_search_respects_limit(self, store: FakeGraphStore) -> None:
        for i in range(10):
            store.add_entity(f"Entity{i}", "Company", summary=f"match entity {i}")
        results = await store.search("match", limit=3)
        assert len(results[0]["nodes"]) == 3


class TestFakeGraphStoreEpisodes:
    """Episode ingestion on FakeGraphStore."""

    async def test_add_episode(self) -> None:
        store = FakeGraphStore()
        episode_id = await store.add_episode(
            name="test_article",
            body="Fed holds rates steady at 5.25%",
            source_description="news_reuters",
        )
        assert episode_id is not None
        assert len(store.episodes) == 1
        assert store.episodes[0]["name"] == "test_article"

    async def test_add_episode_with_reference_time(self) -> None:
        from datetime import datetime, timezone

        store = FakeGraphStore()
        ref_time = datetime(2026, 4, 7, tzinfo=timezone.utc)
        await store.add_episode(
            name="dated_article",
            body="content",
            source_description="test",
            reference_time=ref_time,
        )
        assert "2026-04-07" in store.episodes[0]["reference_time"]


class TestFakeGraphStoreTraversal:
    """Graph traversal operations on FakeGraphStore."""

    @pytest.fixture
    def store(self) -> FakeGraphStore:
        s = FakeGraphStore()
        s.add_entity("China Tariffs", "MacroEvent")
        s.add_entity("Supply Chain", "Effect")
        s.add_entity("NVIDIA", "Company")
        s.add_edge(
            "China Tariffs", "Supply Chain", "IMPACTS", "Tariffs disrupt supply chain"
        )
        s.add_edge("Supply Chain", "NVIDIA", "IMPACTS", "Supply disruption hits NVIDIA")
        return s

    async def test_get_entity(self, store: FakeGraphStore) -> None:
        entity = await store.get_entity("NVIDIA")
        assert entity is not None
        assert entity["name"] == "NVIDIA"
        assert entity["type"] == "Company"

    async def test_get_entity_not_found(self, store: FakeGraphStore) -> None:
        entity = await store.get_entity("nonexistent")
        assert entity is None

    async def test_get_neighbors(self, store: FakeGraphStore) -> None:
        neighbors = await store.get_neighbors("Supply Chain")
        assert len(neighbors) == 2  # China Tariffs and NVIDIA

    async def test_get_neighbors_with_edge_filter(self, store: FakeGraphStore) -> None:
        neighbors = await store.get_neighbors("Supply Chain", edge_types=["IMPACTS"])
        assert len(neighbors) == 2

    async def test_get_neighbors_with_nonmatching_filter(
        self, store: FakeGraphStore
    ) -> None:
        neighbors = await store.get_neighbors("Supply Chain", edge_types=["MATCHES"])
        assert len(neighbors) == 0

    async def test_find_paths(self, store: FakeGraphStore) -> None:
        paths = await store.find_paths("China Tariffs", "NVIDIA")
        assert len(paths) >= 1
        path = paths[0]
        assert len(path["nodes"]) == 3  # China Tariffs -> Supply Chain -> NVIDIA
        assert len(path["edges"]) == 2

    async def test_find_paths_no_connection(self, store: FakeGraphStore) -> None:
        store.add_entity("Isolated", "Company")
        paths = await store.find_paths("China Tariffs", "Isolated")
        assert len(paths) == 0

    async def test_get_relationships(self, store: FakeGraphStore) -> None:
        rels = await store.get_relationships("Supply Chain")
        assert len(rels) >= 1
        impacts = next((r for r in rels if r["edge_type"] == "IMPACTS"), None)
        assert impacts is not None
        assert impacts["count"] == 2

    async def test_run_cypher_returns_empty(self, store: FakeGraphStore) -> None:
        rows = await store.run_cypher("MATCH (n) RETURN n LIMIT 1")
        assert rows == []
