# Task 3: Initialize `layer_cache` in Session Creation

The `start_thinking` endpoint creates sessions. Add `layer_cache: {}` so the field exists from the start.

**Files:**
- Modify: `backend/src/api/thinking.py:101-114` (start endpoint)
- Test: `backend/tests/test_cascade.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_cascade.py`:

```python
class TestSessionInit:
    @pytest.mark.asyncio
    async def test_start_thinking_includes_layer_cache(self):
        mock_col = MagicMock()
        mock_col.insert_one = AsyncMock()

        mock_pools_col = MagicMock()
        mock_pools_col.find_one = AsyncMock(return_value=None)

        def get_col(name):
            return mock_pools_col if name == "pools" else mock_col

        with patch("src.database.mongodb.mongodb") as mock_db:
            mock_db.get_collection.side_effect = get_col

            from src.api.thinking import start_thinking, StartRequest
            await start_thinking(StartRequest(date="2026-03-21"))

            insert_call = mock_col.insert_one.call_args
            session_doc = insert_call[0][0]
            assert "layer_cache" in session_doc
            assert session_doc["layer_cache"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_cascade.py::TestSessionInit -v`
Expected: FAIL — `layer_cache` not in session document

- [ ] **Step 3: Add `layer_cache` to session creation**

In `backend/src/api/thinking.py`, add after `"value_pool": value_items,` (line 113):

```python
        "layer_cache": {},
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_cascade.py::TestSessionInit -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/thinking.py backend/tests/test_cascade.py
git commit -m "feat: initialize layer_cache in new sessions"
```
