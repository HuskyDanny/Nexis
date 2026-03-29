# Lazy-Import Optional Dependencies in Composition Roots

## The Trap
Top-level imports of packages that require Docker services (qdrant-client, fastembed) in composition root files like `dependencies.py`. When `main.py` imports the module during lifespan, these packages must be installed — but the test environment uses mocks and doesn't have them. Result: `ModuleNotFoundError` in unrelated tests that trigger the lifespan (e.g., test_lifespan.py).

## The Solution
Move concrete implementation imports inside the `init_*()` function, not at module level:
```python
# DON'T: top-level import
from src.rag.sparse_encoder import FastEmbedBM25  # pulls in fastembed at import time

# DO: lazy import inside init function
async def init_rag_services():
    from src.rag.sparse_encoder import FastEmbedBM25  # only imported when actually initializing
```

Keep protocol/config imports at module level (they have no heavy deps). Only lazy-import concrete implementations that pull in optional packages.

## Context
- **When this applies:** Any composition root or dependency wiring that imports packages not in the base dev deps
- **Related files:** `backend/src/rag/dependencies.py`
- **Discovered:** 2026-03-26, during node RAG persistence implementation — 2 test failures from fastembed not installed
