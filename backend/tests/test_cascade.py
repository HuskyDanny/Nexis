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


class TestStepCacheWrite:
    """step endpoint should write generated children to layer_cache."""

    @pytest.mark.asyncio
    async def test_step_writes_to_layer_cache(self):
        nodes = [_news("n1"), _news("n2")]
        session = _make_session(nodes, [], layer=0)

        mock_col = MagicMock()
        mock_col.find_one = AsyncMock(return_value=session)
        mock_col.update_one = AsyncMock()

        new_nodes = [_effect("e1", 1, ["n1", "n2"])]
        new_edges = [_edge("n1", "e1"), _edge("n2", "e1")]

        import importlib
        import sys

        if "src.api.thinking" in sys.modules:
            del sys.modules["src.api.thinking"]

        with patch("src.database.mongodb.mongodb") as mock_db, patch(
            "src.services.thinking_service.think_effects", new_callable=AsyncMock
        ) as mock_think:
            mock_db.get_collection.return_value = mock_col
            mock_think.return_value = (new_nodes, new_edges)

            from src.api.thinking import think_step

            await think_step("test_session")

            update_call = mock_col.update_one.call_args_list[-1]
            update_doc = update_call[0][1]
            set_doc = update_doc.get("$set", {})
            expected_hash = parent_set_hash(["n1", "n2"])
            cache_key = f"layer_cache.1.{expected_hash}"
            assert cache_key in set_doc
            assert set_doc[cache_key]["nodes"] == new_nodes
            assert set_doc[cache_key]["edges"] == new_edges


class TestToggleReselect:
    """Re-selecting a node should restore cached children."""

    @pytest.mark.asyncio
    async def test_reselect_restores_cached_children(self):
        n1 = _news("n1", selected=True)
        n2 = _news("n2", selected=False)
        e1 = _effect("e1", 1, ["n1", "n2"], selected=False)
        edges = [_edge("n1", "e1"), _edge("n2", "e1")]

        ps_hash = parent_set_hash(["n1", "n2"])
        cache = {
            "1": {
                ps_hash: {
                    "nodes": [_effect("e1", 1, ["n1", "n2"])],
                    "edges": edges,
                }
            }
        }
        session = _make_session([n1, n2, e1], edges, layer=1, layer_cache=cache)

        mock_col = MagicMock()
        mock_col.find_one = AsyncMock(return_value=session)
        mock_col.update_one = AsyncMock()

        import sys

        if "src.api.thinking" in sys.modules:
            del sys.modules["src.api.thinking"]

        with patch("src.database.mongodb.mongodb") as mock_db:
            mock_db.get_collection.return_value = mock_col

            from src.api.thinking import toggle_node, ToggleRequest

            result = await toggle_node(
                "test_session", "n2", ToggleRequest(selected=True)
            )

            assert n2["selected"] is True
            assert e1["selected"] is True  # restored from cache
            assert result.dirty_count > 0

    @pytest.mark.asyncio
    async def test_reselect_no_cache_no_restore(self):
        n1 = _news("n1", selected=True)
        n2 = _news("n2", selected=False)
        e1 = _effect("e1", 1, ["n1", "n2"], selected=False)
        edges = [_edge("n1", "e1"), _edge("n2", "e1")]

        session = _make_session([n1, n2, e1], edges, layer=1, layer_cache={})

        mock_col = MagicMock()
        mock_col.find_one = AsyncMock(return_value=session)
        mock_col.update_one = AsyncMock()

        import sys

        if "src.api.thinking" in sys.modules:
            del sys.modules["src.api.thinking"]

        with patch("src.database.mongodb.mongodb") as mock_db:
            mock_db.get_collection.return_value = mock_col

            from src.api.thinking import toggle_node, ToggleRequest

            result = await toggle_node(
                "test_session", "n2", ToggleRequest(selected=True)
            )

            assert n2["selected"] is True
            assert e1["selected"] is False  # no cache, stays deselected
            assert result.dirty_count == 0
