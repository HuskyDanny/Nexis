# Task 2: Add `layer_cache` to Session Model

**Files:**
- Modify: `backend/src/models/thinking.py:41-51`
- Test: `backend/tests/test_thinking_models.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_thinking_models.py`:

```python
def test_thinking_session_has_layer_cache_default():
    session = ThinkingSession(date="2026-03-21")
    assert session.layer_cache == {}


def test_thinking_session_layer_cache_stores_data():
    session = ThinkingSession(
        date="2026-03-21",
        layer_cache={
            "1": {
                "abc123def456": {
                    "nodes": [{"id": "e1", "layer": 1}],
                    "edges": [{"source": "n1", "target": "e1"}],
                }
            }
        },
    )
    assert "1" in session.layer_cache
    assert "abc123def456" in session.layer_cache["1"]
    assert len(session.layer_cache["1"]["abc123def456"]["nodes"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_thinking_models.py::test_thinking_session_has_layer_cache_default -v`
Expected: FAIL with `AttributeError: 'ThinkingSession' object has no attribute 'layer_cache'`

- [ ] **Step 3: Add `layer_cache` field**

In `backend/src/models/thinking.py`, add to `ThinkingSession` after `error: str | None = None`:

```python
    layer_cache: dict[str, dict[str, dict]] = Field(default_factory=dict)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_thinking_models.py -v`
Expected: All pass (existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/thinking.py backend/tests/test_thinking_models.py
git commit -m "feat: add layer_cache field to ThinkingSession model"
```
