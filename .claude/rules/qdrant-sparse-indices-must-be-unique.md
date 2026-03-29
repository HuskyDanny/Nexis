# Qdrant Sparse Vector Indices Must Be Unique

## The Trap
Sending sparse vectors with duplicate indices to Qdrant. Hash-based tokenizers can produce collisions (two different words hash to the same index). Qdrant rejects with: `"Validation error: must be unique"`. Unit tests with FakeVectorStore don't catch this — only surfaces against real Qdrant.

## The Solution
Deduplicate sparse indices before upserting. Aggregate weights for colliding tokens:
```python
seen: dict[int, float] = {}
for token in tokens:
    idx = hash(token) % vocab_size
    seen[idx] = seen.get(idx, 0.0) + 1.0
return list(seen.keys()), list(seen.values())
```

## Context
- **When this applies:** Any sparse vector encoder used with Qdrant (FakeSparseEncoder, FastEmbedBM25, or custom)
- **Related files:** `backend/src/rag/fakes.py` (FakeSparseEncoder)
- **Discovered:** 2026-03-26, E2E test — all upserts failed with 422 Unprocessable Entity
