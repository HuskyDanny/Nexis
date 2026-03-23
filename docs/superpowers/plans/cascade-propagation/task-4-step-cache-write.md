# Task 4: Cache Write in Step Endpoint

When `step` generates new children, write them to `layer_cache` so future re-selects can restore them.

**Files:**
- Modify: `backend/src/api/thinking.py:160-199` (step endpoint)
- Create: `backend/tests/test_cascade.py` (with shared helpers)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_cascade.py` with helpers + first test class:

```python
# backend/tests/test_cascade.py
"""Tests for cascade propagation: deselect, re-select (cache), add-from-pool."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.services.cache import parent_set_hash


def _make_session(nodes, edges, layer=0, status="paused", layer_cache=None):
    """Helper to build a session dict matching MongoDB shape."""
    return {
        "id": "test_session", "date": "2026-03-21", "market": "US",
        "max_depth": 3, "nodes": nodes, "edges": edges,
        "status": status, "current_layer": layer, "error": None,
        "news_pool": [], "value_pool": [], "layer_cache": layer_cache or {},
    }


def _news(nid, selected=True):
    return {
        "id": nid, "layer": 0, "type": "news",
        "content": f"News {nid}", "reasoning": "", "sources": [],
        "parents": [], "selected": selected, "metadata": {},
    }


def _effect(eid, layer, parents, selected=True):
    return {
        "id": eid, "layer": layer, "type": "effect",
        "content": f"Effect {eid}", "reasoning": "", "sources": [],
        "parents": parents, "selected": selected, "metadata": {},
    }


def _edge(source, target):
    return {"source": source, "target": target, "relationship": "causes"}


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

        with patch("src.database.mongodb.mongodb") as mock_db, \
             patch("src.services.thinking_service.think_effects", new_callable=AsyncMock) as mock_think:
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_cascade.py::TestStepCacheWrite -v`
Expected: FAIL — `layer_cache` key not in `$set`

- [ ] **Step 3: Add cache write to step endpoint**

In `backend/src/api/thinking.py`, replace the persistence block (lines 181-199) with:

```python
        # Compute cache key from selected parents at current layer
        from src.services.cache import parent_set_hash

        selected_parent_ids = sorted(n["id"] for n in current_layer_nodes)
        ps_hash = parent_set_hash(selected_parent_ids)
        cache_key = f"layer_cache.{next_layer}.{ps_hash}"

        if new_nodes:
            await col.update_one(
                {"id": session_id},
                {
                    "$push": {
                        "nodes": {"$each": new_nodes},
                        "edges": {"$each": new_edges},
                    },
                    "$set": {
                        "current_layer": next_layer,
                        "status": "paused",
                        cache_key: {"nodes": new_nodes, "edges": new_edges},
                    },
                },
            )
        else:
            await col.update_one(
                {"id": session_id},
                {"$set": {"current_layer": next_layer, "status": "paused"}},
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_cascade.py::TestStepCacheWrite -v`
Expected: PASS

- [ ] **Step 5: Run all tests for regressions**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/thinking.py backend/tests/test_cascade.py
git commit -m "feat: step endpoint writes to layer_cache after generating children"
```
