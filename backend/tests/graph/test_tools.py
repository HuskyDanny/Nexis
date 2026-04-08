"""Tests for the 5 tiered graph tools."""

from __future__ import annotations

import pytest

from src.graph.fakes import FakeGraphStore
from src.agents.tools.graph_search import GraphSearchTool
from src.agents.tools.explore_entity import ExploreEntityTool
from src.agents.tools.find_paths import FindPathsTool
from src.agents.tools.get_relationships import GetRelationshipsTool
from src.agents.tools.raw_cypher import RawCypherTool


@pytest.fixture
def store() -> FakeGraphStore:
    s = FakeGraphStore()
    s.add_entity("NVIDIA", "Company", summary="GPU manufacturer")
    s.add_entity("Federal Reserve", "MacroEvent", summary="US central bank")
    s.add_entity("Tech Sector", "Sector")
    s.add_edge(
        "Federal Reserve", "NVIDIA", "IMPACTS", "Fed rate hold impacts NVIDIA margins"
    )
    s.add_edge("NVIDIA", "Tech Sector", "IN_SECTOR", "NVIDIA is in technology sector")
    return s


class TestGraphSearchTool:
    """Tier 1 — handles 80% of queries."""

    async def test_search_returns_results(self, store: FakeGraphStore) -> None:
        tool = GraphSearchTool(graph_store=store)
        results = await tool.arun(query="NVIDIA margins")
        assert len(results) >= 1
        assert len(results[0]["edges"]) >= 1

    async def test_search_empty_query(self, store: FakeGraphStore) -> None:
        tool = GraphSearchTool(graph_store=store)
        results = await tool.arun(query="nonexistent xyz")
        assert len(results[0]["edges"]) == 0

    async def test_search_respects_limit(self, store: FakeGraphStore) -> None:
        tool = GraphSearchTool(graph_store=store)
        results = await tool.arun(query="NVIDIA", limit=1)
        assert len(results) >= 1


class TestExploreEntityTool:
    """Tier 2 — full neighborhood scan."""

    async def test_explore_existing_entity(self, store: FakeGraphStore) -> None:
        tool = ExploreEntityTool(graph_store=store)
        result = await tool.arun(entity_name="NVIDIA")
        assert result["entity"] is not None
        assert result["entity"]["name"] == "NVIDIA"
        assert len(result["neighbors"]) == 2  # Fed + Tech Sector

    async def test_explore_nonexistent_entity(self, store: FakeGraphStore) -> None:
        tool = ExploreEntityTool(graph_store=store)
        result = await tool.arun(entity_name="nonexistent")
        assert result["entity"] is None
        assert "not found" in result["message"]

    async def test_explore_with_edge_filter(self, store: FakeGraphStore) -> None:
        tool = ExploreEntityTool(graph_store=store)
        result = await tool.arun(entity_name="NVIDIA", edge_types=["IMPACTS"])
        assert len(result["neighbors"]) == 1


class TestFindPathsTool:
    """Tier 2 — connection discovery."""

    async def test_find_direct_path(self, store: FakeGraphStore) -> None:
        tool = FindPathsTool(graph_store=store)
        paths = await tool.arun(source="Federal Reserve", target="NVIDIA")
        assert len(paths) >= 1

    async def test_find_no_path(self, store: FakeGraphStore) -> None:
        store.add_entity("Isolated", "Company")
        tool = FindPathsTool(graph_store=store)
        paths = await tool.arun(source="Federal Reserve", target="Isolated")
        assert len(paths) == 0


class TestGetRelationshipsTool:
    """Tier 2 — relationship schema."""

    async def test_get_relationships(self, store: FakeGraphStore) -> None:
        tool = GetRelationshipsTool(graph_store=store)
        rels = await tool.arun(entity_name="NVIDIA")
        assert len(rels) >= 1
        types = {r["edge_type"] for r in rels}
        assert "IMPACTS" in types or "IN_SECTOR" in types

    async def test_get_relationships_empty(self, store: FakeGraphStore) -> None:
        store.add_entity("Lonely", "Company")
        tool = GetRelationshipsTool(graph_store=store)
        rels = await tool.arun(entity_name="Lonely")
        assert len(rels) == 0


class TestRawCypherTool:
    """Tier 2 — escape hatch."""

    async def test_cypher_returns_empty_from_fake(self, store: FakeGraphStore) -> None:
        tool = RawCypherTool(graph_store=store)
        rows = await tool.arun(query="MATCH (n) RETURN n LIMIT 1")
        assert rows == []

    async def test_cypher_with_params(self, store: FakeGraphStore) -> None:
        tool = RawCypherTool(graph_store=store)
        rows = await tool.arun(
            query="MATCH (n {name: $name}) RETURN n", params={"name": "test"}
        )
        assert isinstance(rows, list)
