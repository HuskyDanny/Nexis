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

        # news_entities collection: find().to_list() must return a list (not a coroutine)
        mock_news_col = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_news_col.find.return_value = mock_cursor

        def get_collection(name):
            if name == "pools":
                return mock_pools_col
            if name == "news_entities":
                return mock_news_col
            return mock_col

        mock_mongodb.get_collection = MagicMock(side_effect=get_collection)

        # Reimport to pick up our patched mock
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
        mock_col.find_one_and_update = AsyncMock(return_value=session)
        mock_col.update_one = AsyncMock()

        new_nodes = [_effect("e1", 1, ["n1", "n2"])]
        new_edges = [_edge("n1", "e1"), _edge("n2", "e1")]

        import sys

        if "src.api.thinking" in sys.modules:
            del sys.modules["src.api.thinking"]

        from src.services.thinking_service import LayerResult

        layer_result = LayerResult(
            effect_nodes=new_nodes,
            fetch_nodes=[],
            opportunity_nodes=[],
            all_edges=new_edges,
            controller_decision={"continue": True, "reasoning": "", "summary": "test"},
        )

        with patch("src.database.mongodb.mongodb") as mock_db, patch(
            "src.api.thinking.run_layer", new_callable=AsyncMock
        ) as mock_run_layer:
            mock_db.get_collection.return_value = mock_col
            mock_run_layer.return_value = layer_result

            from src.api.thinking import think_step

            await think_step("test_session")

            update_call = mock_col.update_one.call_args_list[-1]
            update_doc = update_call[0][1]
            set_doc = update_doc.get("$set", {})
            # Verify chain_summaries is stored
            assert "chain_summaries.1" in set_doc


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


class TestToggleDeselect:
    """Deselect BFS cascade should be unchanged (AND-semantics)."""

    @pytest.mark.asyncio
    async def test_deselect_cascades_to_all_descendants(self):
        n1 = _news("n1")
        n2 = _news("n2")
        e1 = _effect("e1", 1, ["n1", "n2"])
        e2 = _effect("e2", 2, ["e1"])
        edges = [_edge("n1", "e1"), _edge("n2", "e1"), _edge("e1", "e2")]

        session = _make_session([n1, n2, e1, e2], edges, layer=2)

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
                "test_session", "n1", ToggleRequest(selected=False)
            )

            assert n1["selected"] is False
            assert e1["selected"] is False
            assert e2["selected"] is False
            assert n2["selected"] is True
            assert result.dirty_count == 2

    @pytest.mark.asyncio
    async def test_deselect_does_not_touch_cache(self):
        n1 = _news("n1")
        e1 = _effect("e1", 1, ["n1"])
        edges = [_edge("n1", "e1")]

        ps_hash = parent_set_hash(["n1"])
        cache = {"1": {ps_hash: {"nodes": [e1.copy()], "edges": edges[:]}}}
        session = _make_session([n1, e1], edges, layer=1, layer_cache=cache)

        mock_col = MagicMock()
        mock_col.find_one = AsyncMock(return_value=session)
        mock_col.update_one = AsyncMock()

        import sys

        if "src.api.thinking" in sys.modules:
            del sys.modules["src.api.thinking"]

        with patch("src.database.mongodb.mongodb") as mock_db:
            mock_db.get_collection.return_value = mock_col

            from src.api.thinking import toggle_node, ToggleRequest

            await toggle_node("test_session", "n1", ToggleRequest(selected=False))

            update_call = mock_col.update_one.call_args
            set_doc = update_call[0][1]["$set"]
            assert "layer_cache" not in set_doc


class TestFullCycle:
    """Integration: deselect → re-select → verify cache restore."""

    @pytest.mark.asyncio
    async def test_deselect_then_reselect_restores_from_cache(self):
        n1 = _news("n1")
        n2 = _news("n2")
        e1 = _effect("e1", 1, ["n1", "n2"])
        edges = [_edge("n1", "e1"), _edge("n2", "e1")]

        ps_hash = parent_set_hash(["n1", "n2"])
        cache = {
            "1": {
                ps_hash: {
                    "nodes": [_effect("e1", 1, ["n1", "n2"])],
                    "edges": edges[:],
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

            # Deselect n1 — e1 cascades off
            await toggle_node("test_session", "n1", ToggleRequest(selected=False))
            assert n1["selected"] is False
            assert e1["selected"] is False

            # Re-fetch session (simulate)
            mock_col.find_one = AsyncMock(return_value=session)

            # Re-select n1 — cache restores e1
            await toggle_node("test_session", "n1", ToggleRequest(selected=True))
            assert n1["selected"] is True
            assert e1["selected"] is True
