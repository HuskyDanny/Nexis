# Task 1: `parent_set_hash` Utility

**Files:**
- Create: `backend/src/services/cache.py`
- Test: `backend/tests/test_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cache.py
from src.services.cache import parent_set_hash


def test_parent_set_hash_deterministic():
    """Same IDs in any order produce the same hash."""
    h1 = parent_set_hash(["b", "a", "c"])
    h2 = parent_set_hash(["c", "a", "b"])
    assert h1 == h2


def test_parent_set_hash_different_sets_differ():
    h1 = parent_set_hash(["a", "b"])
    h2 = parent_set_hash(["a", "c"])
    assert h1 != h2


def test_parent_set_hash_empty():
    h = parent_set_hash([])
    assert isinstance(h, str)
    assert len(h) == 16


def test_parent_set_hash_length():
    h = parent_set_hash(["news_001", "news_002", "news_003"])
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.cache'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/services/cache.py
"""Layer cache utilities for Thinking DAG parent-set memoization."""

import hashlib
import json


def parent_set_hash(selected_parent_ids: list[str]) -> str:
    """Compute a deterministic hash for a set of parent IDs.

    Sorts IDs so order doesn't matter. Returns 16 hex chars.
    """
    key = json.dumps(sorted(selected_parent_ids), separators=(",", ":"))
    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_cache.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/cache.py backend/tests/test_cache.py
git commit -m "feat: parent_set_hash utility for layer cache"
```
