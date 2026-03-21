"""Tests for cascade propagation: deselect, re-select (cache), add-from-pool."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.cache import parent_set_hash


def _make_session(nodes, edges, layer=0, status="paused", layer_cache=None):
    """Helper to build a session dict matching MongoDB shape."""
    return {
        "id": "test_session",
        "date": "2026-03-21",
        "market": "US",
        "max_depth": 3,
        "nodes": nodes,
        "edges": edges,
        "status": status,
        "current_layer": layer,
        "error": None,
        "news_pool": [],
        "value_pool": [],
        "layer_cache": layer_cache or {},
    }


def _news(nid, selected=True):
    return {
        "id": nid,
        "layer": 0,
        "type": "news",
        "content": f"News {nid}",
        "reasoning": "",
        "sources": [],
        "parents": [],
        "selected": selected,
        "metadata": {},
    }


def _effect(eid, layer, parents, selected=True):
    return {
        "id": eid,
        "layer": layer,
        "type": "effect",
        "content": f"Effect {eid}",
        "reasoning": "",
        "sources": [],
        "parents": parents,
        "selected": selected,
        "metadata": {},
    }


def _edge(source, target):
    return {"source": source, "target": target, "relationship": "causes"}


class TestSessionInit:
    @pytest.mark.asyncio
    async def test_start_thinking_includes_layer_cache(self, mock_mongodb):
        # Setup mocks
        mock_col = AsyncMock()
        mock_col.insert_one = AsyncMock()

        mock_pools_col = AsyncMock()
        mock_pools_col.find_one = AsyncMock(return_value=None)

        mock_mongodb.get_collection = MagicMock(
            side_effect=lambda name: mock_pools_col if name == "pools" else mock_col
        )

        # Reimport to pick up our patched mock
        import importlib
        import sys

        if "src.api.thinking" in sys.modules:
            del sys.modules["src.api.thinking"]
        from src.api.thinking import start_thinking, StartRequest

        await start_thinking(StartRequest(date="2026-03-21"))

        insert_call = mock_col.insert_one.call_args
        session_doc = insert_call[0][0]
        assert "layer_cache" in session_doc
        assert session_doc["layer_cache"] == {}
