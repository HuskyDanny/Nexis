# Node RAG & Persistence System

**Date:** 2026-03-26
**Status:** Draft
**Author:** Allen + Claude

## Problem

Every thinking session starts from scratch — fetching news via API, re-deriving effects the pipeline has already reasoned about. Nodes are ephemeral (1hr Redis TTL, session-scoped). Past analysis is lost. This wastes tokens, API budget, and time.

## Solution

A three-layer persistence + RAG system that stores all nodes permanently, indexes them for hybrid search (semantic + keyword), and exposes them as an agent tool. The agent searches existing knowledge before reasoning from scratch.

## Design Principles

1. **Abstractions over implementations** — all services depend on protocols, not concrete classes. Swap Qdrant for Redis Stack, swap SiliconFlow for OpenAI, without touching core logic.
2. **Local-first** — everything runs locally in Docker. No cloud dependencies.
3. **YAGNI** — start with SiliconFlow dense + fastembed BM25 sparse. Upgrade to learned sparse (FlagEmbedding) only if BM25 proves insufficient.
4. **Configurable everything** — all tunable parameters in one `RAGConfig` object, overridable via env vars, benchmarkable by changing one knob.

---

## 1. Data Architecture — Three Layers

### Layer 1: Raw Data Store (MongoDB — existing, no changes)

- `news_entities` — news items, scored, de-duped by cron
- `value_entities` — undervalued stocks, market-scoped

No changes. This layer is the source of raw inputs.

### Layer 2: Node Store (MongoDB — new collection `node_store`)

A flat collection of all nodes ever produced by any session. Decoupled from `thinking_sessions` for independent search.

```python
# node_store document schema
{
    "id": str,                  # 12-char uuid (same as ThinkingNode.id)
    "session_id": str,          # foreign key to thinking_sessions
    "type": str,                # "news" | "effect" | "fetch" | "opportunity"
    "layer": int,               # 0-3
    "content": str,             # text summary
    "reasoning": str,           # agent's explanation
    "confidence": float,        # 0-100
    "parents": list[str],       # parent node IDs (full inference chain)
    "sources": list[str],       # URLs/citations
    "sector": str | None,       # metadata: sector
    "market": str,              # "US" | "CN"
    "date": str,                # session date (YYYY-MM-DD)
    "created_at": datetime,     # UTC timestamp
    "indexed": bool,            # True if successfully indexed in Qdrant
}
```

**MongoDB indexes:**
- `{id: 1}` — unique
- `{session_id: 1}` — find all nodes for a session
- `{indexed: 1}` — find unindexed nodes for reconciliation
- `{created_at: 1}` — prune old nodes

**Why separate from `thinking_sessions`?**
Sessions are complex nested documents (nodes + edges + status + pools). Searching across sessions requires nested array queries — slow and hard to index. `node_store` is flat: one document per node, simple queries, easy to sync.

### Layer 3: Search Index (Qdrant — new service)

Every node in `node_store` is indexed in Qdrant with two vector spaces:

| Vector Space | Model | Dimensions | Purpose |
|---|---|---|---|
| `dense` | SiliconFlow `BAAI/bge-m3` | 1024 | Semantic similarity |
| `sparse` | fastembed `Qdrant/bm25` | Variable (sparse) | Keyword recall |

**Payload fields** (filterable):
- `node_type: str` — "effect", "opportunity", "news", "fetch"
- `sector: str` — "technology", "energy", etc.
- `confidence: float` — 0-100
- `layer: int` — 0-3
- `market: str` — "US", "CN"
- `date: str` — "2026-03-26"
- `session_id: str` — for excluding current session
- `content: str` — stored for display in search results
- `reasoning: str` — stored for display in search results

**Qdrant collection config:**
```python
collection_name = "nodes"
vectors_config = {
    "dense": VectorParams(size=1024, distance=Distance.COSINE),
}
sparse_vectors_config = {
    "sparse": SparseVectorParams(),
}
optimizers_config = OptimizersConfigDiff(
    deleted_threshold=0.2,
    vacuum_min_vector_number=1000,
    default_segment_number=2,
)
hnsw_config = HnswConfigDiff(m=16, ef_construct=100)
```

---

## 2. Node Classification

### First-Class Nodes (Active Session)

Nodes actively in the current session chain:
- User-selected news from the pool
- Effect, fetch, opportunity nodes produced by agents this session
- Anything the pipeline generated in this run

These are the primary input to each layer's reasoning.

### Second-Class Nodes (Historical / RAG Results)

Everything else in the database — prior sessions' effects, old opportunities, historical analysis. Retrieved via RAG as supporting evidence. They are **never promoted** to first-class — the agent cites them in reasoning, but they don't become session nodes.

---

## 3. Write Path

When the Thinker/Matcher produces nodes during a session:

```
Agent produces node
  -> 1. Append to thinking_sessions (existing behavior, unchanged)
  -> 2. Insert into node_store (MongoDB, synchronous, must succeed)
  -> 3. Compute dense embedding (SiliconFlow API, async)
  -> 4. Compute sparse vector (fastembed BM25, in-process, async)
  -> 5. Upsert to Qdrant (dense + sparse + payload, async)
```

Steps 3-5 are **async and non-blocking** via `asyncio.create_task`. If they fail, the node still exists in MongoDB with `indexed: False`.

### Retry & Recovery

| Scenario | Handling |
|---|---|
| Normal write | MongoDB sync, Qdrant async (~<1s) |
| Qdrant down | Node in MongoDB, `indexed: False`. Retry with backoff (configurable retries). |
| Embedding API down | Node in MongoDB, `indexed: False`. Background reconciliation picks it up. |
| Qdrant cold start | Startup reconciliation job: scan `node_store` for `indexed: False`, re-embed and index. |

**Reconciliation job:** Runs on startup + every `reconcile_interval_minutes` (default 30). Finds all nodes where `indexed: False`, computes embeddings, upserts to Qdrant, marks `indexed: True`.

---

## 4. Search Path

### Agent Tool: `SearchNodesTool`

A CrewAI `BaseTool` with structured filter schema:

```python
class SearchNodesTool(BaseTool):
    name: str = "search_nodes"
    description: str = (
        "Search the knowledge base of previously analyzed nodes -- effects, "
        "opportunities, news, and fetch results from prior sessions. "
        "This is fast, free (no API cost), and reuses existing analysis. "
        "Prefer this tool BEFORE fetching live news. Use filters to narrow "
        "results to what's relevant for your current reasoning."
    )

    async def _run(
        self,
        query: str,                              # semantic search text (required)
        node_type: list[str] | None = None,       # filter: ["effect", "opportunity", ...]
        sector: str | None = None,                # filter: "technology", "energy", ...
        min_confidence: int | None = None,         # filter: 0-100
        date_from: str | None = None,             # filter: "2026-03-20"
        date_to: str | None = None,               # filter: "2026-03-26"
        market: str | None = None,                # filter: "US", "CN"
        limit: int = 20,                          # max results
    ) -> list[dict]:
        ...
```

### Search Execution

```
Agent calls search_nodes(query=..., filters=...)
  -> 1. Embed query: SiliconFlow dense (1024d)
  -> 2. Tokenize query: fastembed BM25 (sparse)
  -> 3. Qdrant Query API:
       - Prefetch dense results (prefetch_limit, default 40)
       - Prefetch sparse results (prefetch_limit, default 40)
       - Fuse with RRF (Reciprocal Rank Fusion)
       - Pre-filter by payload conditions (type, sector, confidence, date, market)
       - Exclude current session_id
  -> 4. Apply query-time decay re-ranking
  -> 5. Return top `limit` results to agent
```

**Pre-filtering:** Qdrant narrows candidates by payload filters BEFORE running vector similarity. This is faster and produces better results.

**Over-fetching:** We fetch `prefetch_limit` (default 2x of `limit`) from Qdrant because decay re-ranking changes the order. Newer-but-less-semantically-similar nodes may outrank older-but-more-similar ones after decay.

### Query-Time Decay

Decay is a math operation at retrieval time, not a storage mutation. No writes to Qdrant, no segment rebuilds.

```python
def decay_score(relevance_score, node_date, query_date, node_type):
    half_life = HALF_LIFE_BY_TYPE[node_type]
    age_days = (query_date - node_date).total_seconds() / 86400
    decay = exp(-0.693 * age_days / half_life)
    return relevance_score * decay
```

**Half-lives by node type:**

| Node Type | Half-Life (days) | Rationale |
|---|---|---|
| `news` | 3 | News is perishable |
| `effect` | 7 | Market effects take time to play out |
| `opportunity` | 5 | Stock opportunities shift with price |
| `fetch` | 3 | Research queries tied to news cycle |

### Search Result Format

```python
{
    "id": "a1b2c3d4e5f6",
    "type": "effect",
    "content": "Fed rate pause reduces borrowing costs for fintech lenders...",
    "reasoning": "Historical pattern: 2024 rate pause led to 15% increase...",
    "confidence": 78,
    "sector": "technology",
    "date": "2026-03-24",
    "parents": ["news_xyz", "effect_abc"],
    "score": 0.87,  # final score after RRF + decay
}
```

---

## 5. Agent Integration

### Tool Priority

The Thinker agent gets two tools:

| Tool | Cost | Speed | Use When |
|---|---|---|---|
| `search_nodes` | Free | ~50ms | First stop -- check existing knowledge |
| `fetch_news` | API tokens | ~1-2s | When search_nodes doesn't cover the gap |

### Agent Skill (System Prompt)

```
## Skill: Knowledge Reuse (search_nodes)

You have access to a knowledge base of nodes from prior analysis sessions --
effects, opportunities, news summaries, and research results.

WHEN TO USE:
- Before reasoning from scratch, check if similar analysis already exists
- When you identify an information gap, search before calling fetch_news
- When a sector or theme has been analyzed before

HOW TO USE:
- Start broad (just a query), then narrow with filters if too many results
- Use node_type filter to find specific kinds of prior work
- Use min_confidence to surface only high-quality prior analysis
- The results include full reasoning chains -- read them to avoid re-deriving

WHAT TO DO WITH RESULTS:
- If a prior effect is still valid and relevant: cite it in your reasoning,
  reference its ID, and build on it rather than re-deriving from scratch
- If a prior effect is outdated or your current news contradicts it:
  reason fresh, note the contradiction
- Prior nodes are supporting evidence, not first-class session nodes
```

---

## 6. Garbage Collection

### Pruning

Daily cron job removes nodes older than `prune_max_age_days` (default 90):

1. Query MongoDB `node_store` for `created_at < cutoff`
2. Delete matching IDs from Qdrant (soft-delete, immediate)
3. Delete matching documents from MongoDB

At 90 days, decay factor is ~0.0001 -- effectively invisible in search.

### Qdrant HNSW Maintenance

Qdrant manages HNSW automatically via its segment optimizer:
- New inserts go to a write-ahead segment (no HNSW rebuild)
- Deletes are soft-deletes (flag flip, no rebuild)
- Background segment merge triggers when >20% of a segment is deleted
- Merge rebuilds HNSW only for the merged segment, non-blocking

At our scale (~50k nodes, ~200 inserts/day, ~200 prunes/day), the optimizer handles this without intervention.

---

## 7. Infrastructure

### Docker Compose Addition

```yaml
qdrant:
  image: qdrant/qdrant:v1.14.0
  ports:
    - "6333:6333"
    - "6334:6334"
  volumes:
    - qdrant_data:/qdrant/storage
  environment:
    QDRANT__SERVICE__GRPC_PORT: 6334
  restart: unless-stopped
```

Backend env:
```yaml
QDRANT_URL: http://qdrant:6333
```

### Port Convention

| Service | Port | Notes |
|---|---|---|
| Backend | 8000 | Existing |
| Frontend | 3000 | Existing |
| MongoDB | 27017 | Existing |
| Redis | 6379 | Existing |
| Qdrant HTTP | 6333 | New |
| Qdrant gRPC | 6334 | New |

Qdrant is shared across worktrees (like MongoDB).

### New Python Dependencies

```toml
[project]
dependencies = [
    "qdrant-client>=1.14.0",
    "fastembed>=0.5.0",
]
```

### Embedding Models

| Component | Model | Source | Dimensions |
|---|---|---|---|
| Dense embedding | `BAAI/bge-m3` | SiliconFlow API | 1024 |
| Sparse encoding | `Qdrant/bm25` | fastembed (local) | Variable |

**Upgrade path:** If BM25 sparse proves insufficient, swap fastembed for `FlagEmbedding` (learned sparse from bge-m3). The Qdrant schema is the same -- just re-index.

---

## 8. Configuration

Centralized `RAGConfig` with env var overrides:

```python
class RAGConfig(BaseSettings):
    # Embedding
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024

    # Search
    dense_weight: float = 1.0
    sparse_weight: float = 1.0
    prefetch_limit: int = 40
    default_limit: int = 20

    # Decay half-lives (days)
    decay_half_life_news: float = 3.0
    decay_half_life_effect: float = 7.0
    decay_half_life_opportunity: float = 5.0
    decay_half_life_fetch: float = 3.0

    # Qdrant HNSW
    hnsw_m: int = 16
    hnsw_ef_construct: int = 100

    # Pruning
    prune_max_age_days: int = 90
    prune_interval_minutes: int = 30

    # Reconciliation
    reconcile_on_startup: bool = True
    reconcile_interval_minutes: int = 30

    # Retry
    index_retry_count: int = 2
    index_retry_delay_seconds: float = 1.0

    class Config:
        env_prefix = "RAG_"
```

All parameters benchmarkable via env vars:
```bash
RAG_DECAY_HALF_LIFE_EFFECT=3.0 pytest tests/benchmark/test_search_quality.py
```

---

## 9. Dependency Injection

### Protocols

```python
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

class SparseEncoder(Protocol):
    def encode(self, text: str) -> tuple[list[int], list[float]]: ...

class VectorStore(Protocol):
    async def upsert(self, collection: str, points: list) -> None: ...
    async def query(self, collection: str, dense: list[float],
                    sparse: tuple, filters: dict, limit: int) -> list[dict]: ...
    async def delete(self, collection: str, ids: list[str]) -> None: ...

class NodeRepository(Protocol):
    async def insert(self, doc: dict) -> None: ...
    async def find_unindexed(self) -> list[dict]: ...
    async def delete_older_than(self, cutoff: datetime) -> int: ...
```

### Concrete Implementations

| Protocol | Implementation | Notes |
|---|---|---|
| `EmbeddingProvider` | `SiliconFlowEmbedding` | API call to SiliconFlow |
| `SparseEncoder` | `FastEmbedBM25` | Local fastembed, no network |
| `VectorStore` | `QdrantVectorStore` | Qdrant client wrapper |
| `NodeRepository` | `MongoNodeStoreRepo` | Motor async, `node_store` collection |

### Test Fakes

| Protocol | Fake | Behavior |
|---|---|---|
| `EmbeddingProvider` | `FakeEmbedding` | Deterministic vector from text hash |
| `SparseEncoder` | `FakeSparseEncoder` | Word-split tokenization |
| `VectorStore` | `FakeVectorStore` | In-memory dict, brute-force search |
| `NodeRepository` | `FakeNodeRepo` | In-memory dict |

### Composition Root

```python
# backend/src/dependencies.py
def create_rag_services(config: RAGConfig):
    embedder = SiliconFlowEmbedding(model=config.embedding_model)
    sparse = FastEmbedBM25()
    vector_store = QdrantVectorStore(url=settings.QDRANT_URL)
    node_repo = MongoNodeStoreRepo(db=mongodb.db)
    return (
        NodePersistenceService(node_repo, vector_store, embedder, sparse, config),
        NodeSearchService(vector_store, embedder, sparse, config),
    )
```

---

## 10. File Structure

```
backend/src/
  database/
    mongodb.py              # existing
    redis.py                # existing
    qdrant.py               # new -- QdrantVectorStore (implements VectorStore)
    repositories/
      node_store_repo.py    # new -- MongoNodeStoreRepo (implements NodeRepository)
  services/
    thinking_service.py     # existing -- calls NodePersistenceService after node creation
    session_cache.py        # existing
    embedding.py            # new -- SiliconFlowEmbedding (implements EmbeddingProvider)
    sparse_encoder.py       # new -- FastEmbedBM25 (implements SparseEncoder)
    node_persistence.py     # new -- NodePersistenceService (dual-write + retry)
    node_search.py          # new -- NodeSearchService (search + decay + re-rank)
    rag_config.py           # new -- RAGConfig
  agents/
    tools/
      fetch_news.py         # existing
      search_nodes.py       # new -- SearchNodesTool (CrewAI BaseTool)
    thinking_crew.py        # existing -- add SearchNodesTool to Thinker agent
  dependencies.py           # new -- composition root
  cron/
    scheduler.py            # existing -- add prune_stale_nodes + reconcile_index jobs
```

---

## 11. Testing Strategy

### Unit Tests (No Docker, fakes only)

| Test | Verifies |
|---|---|
| `test_embedding_service` | Returns 1024d vector, handles API errors |
| `test_sparse_encoder` | Produces valid sparse vectors, handles empty strings |
| `test_persist_node_writes_both` | Node in MongoDB AND vector store after persist |
| `test_persist_survives_vector_store_failure` | Node in MongoDB with `indexed: False` when Qdrant down |
| `test_decay_scoring_math` | Exponential decay correct per node type half-life |
| `test_decay_half_life_boundary` | Score = 0.5 at exactly half-life days |
| `test_search_filters_applied` | Each filter narrows results correctly |
| `test_search_excludes_current_session` | Current session nodes never returned |
| `test_reconcile_finds_unindexed` | Unindexed nodes get picked up and indexed |
| `test_prune_removes_old_nodes` | Nodes older than cutoff deleted from both stores |
| `test_config_env_override` | `RAG_DECAY_HALF_LIFE_EFFECT=3.0` overrides default |

### Integration Tests (Docker required)

| Test | Verifies |
|---|---|
| `test_search_nodes_tool_e2e` | Full tool call returns ranked, decayed results |
| `test_hybrid_search_quality` | Dense finds semantic, sparse finds keywords, RRF combines |
| `test_write_then_search` | Insert node, immediately searchable |
| `test_cold_start_reconcile` | Restart Qdrant, reconcile rebuilds index |

### Benchmark Tests (Search Quality)

**Golden set:** Manually labeled query-node relevance pairs.

**Metrics:**

| Metric | Target | Purpose |
|---|---|---|
| NDCG@20 | >= 0.7 | Primary: relevant results ranked high |
| Recall@20 | >= 0.8 | Safety net: don't miss relevant nodes |
| MRR | >= 0.5 | Practical: first relevant in top 2 |

**Benchmark tests:**
- `test_ndcg_at_20` -- NDCG >= 0.7 for hybrid search
- `test_recall_at_20` -- Recall >= 0.8
- `test_mrr` -- MRR >= 0.5
- `test_hybrid_beats_dense_only` -- Hybrid NDCG > dense-only for keyword queries
- `test_hybrid_beats_sparse_only` -- Hybrid NDCG > sparse-only for paraphrase queries
- `test_decay_improves_freshness` -- Newer relevant nodes rank above older equivalents

All benchmarks parameterized by `RAGConfig` for systematic tuning.

---

## 12. Migration

Existing `thinking_sessions` data stays as-is. No migration of historical sessions -- the node store starts empty and populates going forward. Old sessions continue to work through the existing API.

If historical backfill is desired later: a one-time script extracts nodes from `thinking_sessions` into `node_store` and indexes them.
