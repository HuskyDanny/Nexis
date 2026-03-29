# Qdrant Requires UUID or Integer Point IDs

## The Trap
Passing arbitrary string IDs (e.g., `"n1"`, `"eff_001"`) as Qdrant point IDs. Qdrant rejects them with: `"value n1 is not a valid point ID, valid values are either an unsigned integer or a UUID"`. This only surfaces at runtime against a real Qdrant instance — unit tests with FakeVectorStore accept any string.

## The Solution
Convert string node IDs to deterministic UUID5s before upserting to Qdrant. Store the original ID in the payload for round-tripping:
```python
import uuid
_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

def _str_to_uuid(s: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, s))

# Upsert: id=_str_to_uuid(node_id), payload={..., "_original_id": node_id}
# Query: pop "_original_id" from payload, return as the result ID
# Delete: convert IDs to UUIDs before passing to Qdrant
```

## Context
- **When this applies:** Any code that upserts/deletes points in Qdrant using string IDs
- **Related files:** `backend/src/rag/qdrant_store.py`
- **Discovered:** 2026-03-26, during Qdrant integration tests — all 10 upsert/query/delete tests failed with 400 Bad Request
