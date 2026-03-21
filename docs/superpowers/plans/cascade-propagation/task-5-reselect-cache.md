# Task 5: Re-select with Cache Restore

The toggle endpoint's re-select path: compute parent-set hash, check cache, flip matching nodes back to `selected: true`.

**Files:**
- Modify: `backend/src/api/thinking.py:223-279` (toggle endpoint)
- Test: `backend/tests/test_cascade.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_cascade.py`:

```python
class TestToggleReselect:
    """Re-selecting a node should restore cached children."""

    @pytest.mark.asyncio
    async def test_reselect_restores_cached_children(self):
        n1 = _news("n1", selected=True)
        n2 = _news("n2", selected=False)
        e1 = _effect("e1", 1, ["n1", "n2"], selected=False)
        edges = [_edge("n1", "e1"), _edge("n2", "e1")]

        ps_hash = parent_set_hash(["n1", "n2"])
        cache = {"1": {ps_hash: {
            "nodes": [_effect("e1", 1, ["n1", "n2"])],
            "edges": edges,
        }}}
        session = _make_session([n1, n2, e1], edges, layer=1, layer_cache=cache)

        mock_col = MagicMock()
        mock_col.find_one = AsyncMock(return_value=session)
        mock_col.update_one = AsyncMock()

        with patch("src.database.mongodb.mongodb") as mock_db:
            mock_db.get_collection.return_value = mock_col

            from src.api.thinking import toggle_node, ToggleRequest
            result = await toggle_node("test_session", "n2", ToggleRequest(selected=True))

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

        with patch("src.database.mongodb.mongodb") as mock_db:
            mock_db.get_collection.return_value = mock_col

            from src.api.thinking import toggle_node, ToggleRequest
            result = await toggle_node("test_session", "n2", ToggleRequest(selected=True))

            assert n2["selected"] is True
            assert e1["selected"] is False  # no cache, stays deselected
            assert result.dirty_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_cascade.py::TestToggleReselect -v`
Expected: FAIL — current toggle doesn't restore children on re-select

- [ ] **Step 3: Implement re-select cache path**

In `backend/src/api/thinking.py`, replace toggle logic (lines 245-270) with:

```python
    target_node["selected"] = req.selected

    dirty_count = 0
    if not req.selected:
        # === DESELECT: BFS cascade (existing, unchanged) ===
        dirty_ids = set()
        queue = [node_id]
        edge_map: dict[str, list[str]] = {}
        for e in session["edges"]:
            edge_map.setdefault(e["source"], []).append(e["target"])

        while queue:
            current = queue.pop(0)
            for child in edge_map.get(current, []):
                if child not in dirty_ids:
                    dirty_ids.add(child)
                    queue.append(child)

        for n in nodes:
            if n["id"] in dirty_ids:
                n["selected"] = False
                dirty_count += 1

    else:
        # === RE-SELECT: check cache layer by layer ===
        from src.services.cache import parent_set_hash

        layer_cache = session.get("layer_cache", {})
        target_layer = target_node["layer"]
        max_layer = max((n["layer"] for n in nodes), default=0)

        for check_layer in range(target_layer + 1, max_layer + 1):
            selected_parents = sorted(
                n["id"] for n in nodes
                if n["selected"] and n["layer"] == check_layer - 1
            )
            ps_hash = parent_set_hash(selected_parents)

            cached = layer_cache.get(str(check_layer), {}).get(ps_hash)
            if not cached:
                break

            cached_ids = {cn["id"] for cn in cached["nodes"]}
            for n in nodes:
                if n["id"] in cached_ids and not n["selected"]:
                    n["selected"] = True
                    dirty_count += 1

    await col.update_one({"id": session_id}, {"$set": {"nodes": nodes}})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_cascade.py::TestToggleReselect -v`
Expected: 2 passed

- [ ] **Step 5: Run all tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/thinking.py backend/tests/test_cascade.py
git commit -m "feat: re-select restores cached children via parent-set hash lookup"
```
