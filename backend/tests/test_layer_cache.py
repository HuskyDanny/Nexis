"""Tests for layer_cache round-trip: write (think_step) → read (toggle_node re-select)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.cache import parent_set_hash


# --- Helpers ---


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


def _make_session(nodes, edges, layer=0, status="paused", layer_cache=None):
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
        "layer_cache": layer_cache if layer_cache is not None else {},
        "chain_summaries": {},
        "confidence_threshold": 35,
    }


# --- Tests ---


class TestLayerCacheWrite:
    """think_step must write layer_cache in nested dict format: {str(layer): {ps_hash: {nodes, edges}}}."""

    @pytest.mark.asyncio
    async def test_step_writes_layer_cache_nested_dict(self):
        """Cache write must produce nested dict {str(layer): {ps_hash: data}} in MongoDB."""
        import sys

        if "src.api.thinking" in sys.modules:
            del sys.modules["src.api.thinking"]

        nodes = [_news("n1"), _news("n2")]
        session = _make_session(nodes, [], layer=0)

        new_nodes = [_effect("e1", 1, ["n1", "n2"])]
        new_edges = [_edge("n1", "e1"), _edge("n2", "e1")]

        mock_col = MagicMock()
        mock_col.find_one_and_update = AsyncMock(return_value=session)
        mock_col.update_one = AsyncMock()

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

        # Inspect all update_one calls to find the layer_cache write
        all_set_docs = [
            call[0][1].get("$set", {}) for call in mock_col.update_one.call_args_list
        ]

        # The cache should be written as nested dict key: layer_cache.<layer>.<hash>
        # where MongoDB dot-notation creates: {"layer_cache": {"1": {"<hash>": {...}}}}
        # OR stored directly as "layer_cache.1.<hash>" key — we test by checking
        # what key format was used.
        #
        # Expected (correct): "$set": {"layer_cache.1": {"<ps_hash>": {nodes, edges}}}
        # OR:                 "$set": {"layer_cache": {"1": {"<ps_hash>": {...}}}}
        # Wrong (old bug):    "$set": {"layer_cache.1.<ps_hash>": {...}}

        ps_hash = parent_set_hash(["n1", "n2"])

        found_correct_write = False
        found_flat_write = False

        for set_doc in all_set_docs:
            # Check for correct nested format: "layer_cache.1" -> {hash: data}
            layer_key = "layer_cache.1"
            if layer_key in set_doc:
                val = set_doc[layer_key]
                if isinstance(val, dict) and ps_hash in val:
                    found_correct_write = True

            # Check for flat (buggy) format: "layer_cache.1.<ps_hash>" -> data
            flat_key = f"layer_cache.1.{ps_hash}"
            if flat_key in set_doc:
                found_flat_write = True

        assert not found_flat_write, (
            f"Cache write used flat key 'layer_cache.1.{ps_hash}' — "
            "this prevents the read path from finding it. "
            "Write must use 'layer_cache.1' -> {{ps_hash: data}} instead."
        )
        assert found_correct_write, (
            f"Cache write did not store data under 'layer_cache.1' -> {{'{ps_hash}': {{nodes, edges}}}}. "
            f"Actual $set docs: {all_set_docs}"
        )


class TestLayerCacheRoundTrip:
    """Full round-trip: step writes cache, toggle_node re-select reads it back."""

    @pytest.mark.asyncio
    async def test_cache_hit_restores_nodes(self):
        """When layer_cache has the matching hash, re-selecting restores children."""
        import sys

        if "src.api.thinking" in sys.modules:
            del sys.modules["src.api.thinking"]

        n1 = _news("n1", selected=True)
        n2 = _news("n2", selected=False)  # was deselected
        e1 = _effect("e1", 1, ["n1", "n2"], selected=False)  # cascade-deselected
        edges = [_edge("n1", "e1"), _edge("n2", "e1")]

        ps_hash = parent_set_hash(["n1", "n2"])
        # Cache in the correct nested format that the read path expects
        layer_cache = {
            "1": {
                ps_hash: {
                    "nodes": [_effect("e1", 1, ["n1", "n2"])],
                    "edges": edges[:],
                }
            }
        }
        session = _make_session([n1, n2, e1], edges, layer=1, layer_cache=layer_cache)

        mock_col = MagicMock()
        mock_col.find_one = AsyncMock(return_value=session)
        mock_col.update_one = AsyncMock()

        with patch("src.database.mongodb.mongodb") as mock_db:
            mock_db.get_collection.return_value = mock_col

            from src.api.thinking import toggle_node, ToggleRequest

            result = await toggle_node(
                "test_session", "n2", ToggleRequest(selected=True)
            )

        assert n2["selected"] is True, "n2 should be selected after toggle"
        assert e1["selected"] is True, "e1 should be restored from cache"
        assert result.dirty_count >= 1, "At least e1 should be marked dirty"

    @pytest.mark.asyncio
    async def test_cache_miss_does_not_restore(self):
        """When layer_cache has no matching hash, re-select does not restore children."""
        import sys

        if "src.api.thinking" in sys.modules:
            del sys.modules["src.api.thinking"]

        n1 = _news("n1", selected=True)
        n2 = _news("n2", selected=False)
        e1 = _effect("e1", 1, ["n1", "n2"], selected=False)
        edges = [_edge("n1", "e1"), _edge("n2", "e1")]

        # Empty cache — no entries
        session = _make_session([n1, n2, e1], edges, layer=1, layer_cache={})

        mock_col = MagicMock()
        mock_col.find_one = AsyncMock(return_value=session)
        mock_col.update_one = AsyncMock()

        with patch("src.database.mongodb.mongodb") as mock_db:
            mock_db.get_collection.return_value = mock_col

            from src.api.thinking import toggle_node, ToggleRequest

            result = await toggle_node(
                "test_session", "n2", ToggleRequest(selected=True)
            )

        assert n2["selected"] is True, "n2 should be selected after toggle"
        assert e1["selected"] is False, "e1 should NOT be restored (cache miss)"
        assert result.dirty_count == 0, "No nodes should be dirty (cache miss)"

    @pytest.mark.asyncio
    async def test_cache_hash_mismatch_does_not_restore(self):
        """Cache entry for wrong parent set does not restore children."""
        import sys

        if "src.api.thinking" in sys.modules:
            del sys.modules["src.api.thinking"]

        n1 = _news("n1", selected=True)
        n2 = _news("n2", selected=False)
        e1 = _effect("e1", 1, ["n1", "n2"], selected=False)
        edges = [_edge("n1", "e1"), _edge("n2", "e1")]

        # Cache only has entry for a DIFFERENT parent set
        wrong_hash = parent_set_hash(["n1"])  # only n1, not both
        layer_cache = {
            "1": {
                wrong_hash: {
                    "nodes": [_effect("e1", 1, ["n1", "n2"])],
                    "edges": edges[:],
                }
            }
        }
        session = _make_session([n1, n2, e1], edges, layer=1, layer_cache=layer_cache)

        mock_col = MagicMock()
        mock_col.find_one = AsyncMock(return_value=session)
        mock_col.update_one = AsyncMock()

        with patch("src.database.mongodb.mongodb") as mock_db:
            mock_db.get_collection.return_value = mock_col

            from src.api.thinking import toggle_node, ToggleRequest

            result = await toggle_node(
                "test_session", "n2", ToggleRequest(selected=True)
            )

        assert n2["selected"] is True
        assert e1["selected"] is False, "Hash mismatch — should NOT restore"
        assert result.dirty_count == 0
