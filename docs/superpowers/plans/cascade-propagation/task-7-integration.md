# Task 7: Integration Test — Full Deselect → Re-select Cycle

End-to-end test: verify children are restored from cache after a deselect → re-select cycle.

**Files:**
- Test: `backend/tests/test_cascade.py`

- [ ] **Step 1: Write the integration test**

Append to `backend/tests/test_cascade.py`:

```python
class TestFullCycle:
    """Integration: deselect → re-select → verify cache restore."""

    @pytest.mark.asyncio
    async def test_deselect_then_reselect_restores_from_cache(self):
        n1 = _news("n1")
        n2 = _news("n2")
        e1 = _effect("e1", 1, ["n1", "n2"])
        edges = [_edge("n1", "e1"), _edge("n2", "e1")]

        ps_hash = parent_set_hash(["n1", "n2"])
        cache = {"1": {ps_hash: {
            "nodes": [_effect("e1", 1, ["n1", "n2"])],
            "edges": edges[:],
        }}}
        session = _make_session([n1, n2, e1], edges, layer=1, layer_cache=cache)

        mock_col = MagicMock()
        mock_col.find_one = AsyncMock(return_value=session)
        mock_col.update_one = AsyncMock()

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
```

- [ ] **Step 2: Run test**

Run: `cd backend && python -m pytest tests/test_cascade.py::TestFullCycle -v`
Expected: PASS

- [ ] **Step 3: Run all tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_cascade.py
git commit -m "test: integration test for full deselect → re-select cache cycle"
```
