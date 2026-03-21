# Task 6: Deselect Cascade Regression Tests

Verify the existing BFS deselect still works correctly after our changes to the toggle endpoint.

**Files:**
- Test: `backend/tests/test_cascade.py`

- [ ] **Step 1: Write the tests**

Append to `backend/tests/test_cascade.py`:

```python
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

        with patch("src.database.mongodb.mongodb") as mock_db:
            mock_db.get_collection.return_value = mock_col

            from src.api.thinking import toggle_node, ToggleRequest
            result = await toggle_node("test_session", "n1", ToggleRequest(selected=False))

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

        with patch("src.database.mongodb.mongodb") as mock_db:
            mock_db.get_collection.return_value = mock_col

            from src.api.thinking import toggle_node, ToggleRequest
            await toggle_node("test_session", "n1", ToggleRequest(selected=False))

            update_call = mock_col.update_one.call_args
            set_doc = update_call[0][1]["$set"]
            assert "layer_cache" not in set_doc
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/test_cascade.py::TestToggleDeselect -v`
Expected: 2 passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_cascade.py
git commit -m "test: verify deselect cascade preserves existing behavior"
```
