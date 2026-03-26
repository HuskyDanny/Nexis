"""Tests for SearchNodesTool CrewAI wrapper."""

import pytest

from src.rag.search import NodeSearchService
from src.agents.tools.search_nodes import SearchNodesTool


@pytest.fixture
def search_service(fake_store, fake_embedding, fake_sparse, rag_config):
    return NodeSearchService(fake_store, fake_embedding, fake_sparse, rag_config)


@pytest.fixture
def tool(search_service):
    return SearchNodesTool(search_service=search_service, session_id="current_session")


class TestSearchNodesTool:
    def test_tool_name(self, tool):
        assert tool.name == "search_nodes"

    def test_tool_has_description(self, tool):
        assert (
            "knowledge base" in tool.description.lower()
            or "search" in tool.description.lower()
        )

    async def test_arun_basic(self, tool):
        result = await tool.arun(query="Fed rate impact")
        assert isinstance(result, list)

    async def test_arun_with_filters(
        self, tool, fake_store, fake_embedding, fake_sparse
    ):
        dense = await fake_embedding.embed("tariff semiconductor")
        indices, values = fake_sparse.encode("tariff semiconductor")
        await fake_store.upsert(
            "nodes",
            [
                {
                    "id": "eff1",
                    "vector": {"dense": dense, "sparse": (indices, values)},
                    "payload": {
                        "node_type": "effect",
                        "sector": "technology",
                        "confidence": 80,
                        "market": "US",
                        "date": "2026-03-25",
                        "session_id": "other",
                        "content": "Tariff on semiconductors",
                        "reasoning": "Supply chain impact",
                    },
                }
            ],
        )

        result = await tool.arun(
            query="tariff semiconductor",
            node_type="effect",
            sector="technology",
            min_confidence=70,
        )
        assert len(result) >= 1
        assert result[0]["id"] == "eff1"

    def test_run_sync_wrapper(self, tool):
        result = tool._run(query="test query")
        assert isinstance(result, list)
