# Quality Gates: Qdrant → Graphiti/Neo4j Migration

## Codebase Baseline Summary

| Metric | Current Value |
|--------|--------------|
| Total test functions | 552 |
| Test categories | root (240), benchmark (179), rag (67), api (28), pipelines (12), core (7) |
| RAG-specific tests | 67 (protocols, search, persistence, decay, config, e2e pipeline, Qdrant integration, search_nodes tool) |
| Benchmark scenarios | 2 (Iran Escalation, Fed Rate Decision) |
| Benchmark grade | B (≥0.70) |
| RAG search baseline | NDCG@20=0.611, Recall@20=1.0, MRR=0.572 (FakeEmbedding hash-based) |
| Protocols | VectorStore, EmbeddingProvider, SparseEncoder, NodeRepository (all @runtime_checkable) |
| Fakes | FakeVectorStore, FakeEmbedding, FakeSparseEncoder, FakeNodeRepo |
| Persistence model | Dual-write: MongoDB sync (source of truth) + Qdrant async (search index) |
| Agent tools | SearchNodesTool (RAG search), FetchNewsTool (live news) |

---

## Gate 1: Search Quality

### 1.1 Core Retrieval Metrics (relative to Qdrant baseline)

| Metric | Qdrant Baseline | Minimum Target | Stretch Target |
|--------|----------------|----------------|----------------|
| NDCG@20 | 0.611 | **≥ 0.55** (-10%) | ≥ 0.65 (+6%) |
| Recall@20 | 1.0 | **≥ 0.90** | ≥ 0.95 |
| MRR | 0.572 | **≥ 0.50** (-12%) | ≥ 0.60 (+5%) |

**Rationale:** A small regression is acceptable because Graphiti's value lies in relationship-aware retrieval, not raw vector similarity. The graph adds a new search dimension (traversal) that these metrics don't capture. However, flat retrieval must not degrade catastrophically.

**Pass/Fail:** ALL three minimum targets must pass simultaneously. Missing any one is a FAIL.

### 1.2 Graph-Specific Metrics (NEW — no baseline)

| Metric | Minimum Target | How to Measure |
|--------|----------------|----------------|
| Entity resolution accuracy | **≥ 0.85** | Golden set of 20 entities with known aliases (e.g., "Fed" = "Federal Reserve" = "FOMC"). Measure: correct_merges / (correct_merges + false_splits + false_merges) |
| Path discovery correctness | **≥ 0.80** | 10 causal chains from scenarios with known 2-hop paths. Measure: correctly_discovered_paths / total_expected_paths |
| Temporal filtering accuracy | **≥ 0.95** | 10 queries with valid_at/invalid_at constraints. Measure: results_within_time_window / total_results |
| Edge type correctness | **≥ 0.90** | 15 known relationships. Measure: correct_edge_type / total_edges_created |

**Pass/Fail:** Each metric independently. Entity resolution and temporal filtering are HARD gates (must pass). Path discovery and edge type are SOFT gates (failure triggers review, not block).

### 1.3 Golden Set Extension

The existing golden set (`backend/tests/benchmark/rag/golden_set.py`) has 10 SEED_NODES and 6 GOLDEN_QUERIES. For graph testing, extend with:

- **10 additional nodes** with explicit relationships (causal chains, entity references)
- **4 graph-specific queries** testing traversal:
  1. "What effects does Fed rate decision cause?" (1-hop traversal)
  2. "What opportunities arise from oil supply disruption?" (2-hop: news → effect → opportunity)
  3. "Find all entities related to NVIDIA" (entity fan-out)
  4. "What changed between March 20 and March 25?" (temporal window)

---

## Gate 2: Performance

### 2.1 Async Write Latency

| Operation | Max Added Latency | Measurement Point |
|-----------|-------------------|-------------------|
| persist_node (user-facing) | **≤ 50ms p95** added vs current | Time from `persist_node()` call to MongoDB write completion (graph write is async, same pattern as current Qdrant async) |
| Background graph write | **≤ 2000ms p95** | Time for `_background_index()` equivalent to complete graph entity+edge creation |
| persist_batch (5 nodes) | **≤ 300ms p95** | End-to-end for 5-node batch with semaphore(5) |

**Rationale:** The current dual-write pattern (MongoDB sync + Qdrant async) means user-facing latency is MongoDB-bound. Graph writes replace Qdrant async writes. The user must not notice the switch.

**Pass/Fail:** User-facing latency is a HARD gate. Background write latency is SOFT (can be tuned post-launch).

### 2.2 Search Latency

| Operation | Target p95 | Measurement |
|-----------|-----------|-------------|
| Graph search (simple query) | **≤ 500ms** | Single semantic search equivalent to current `NodeSearchService.search()` |
| Graph search (with traversal) | **≤ 1500ms** | Query + 2-hop traversal + result assembly |
| Graph search (with temporal filter) | **≤ 800ms** | Search with valid_at/invalid_at constraints |

**Pass/Fail:** Simple query is HARD. Traversal and temporal are SOFT.

### 2.3 Resource Consumption

| Resource | Target | Measurement |
|----------|--------|-------------|
| Neo4j Docker memory | **≤ 1GB** idle, **≤ 2GB** under load | `docker stats` during benchmark run |
| Neo4j Docker CPU | **≤ 30%** idle (single core) | `docker stats` during 60s idle period |
| Startup time (graph init) | **≤ 10s** | Time from `init_rag_services()` start to completion (includes Neo4j connection, schema setup) |
| Total Docker memory (all services) | **≤ 4GB** | MongoDB + Redis + Neo4j + Backend combined |

**Pass/Fail:** All SOFT gates — document actual values, flag if exceeded.

---

## Gate 3: Regression

### 3.1 Existing Test Suite

| Category | Count | Requirement |
|----------|-------|-------------|
| Root tests | 240 | **ALL must pass** (none touch Qdrant directly) |
| Benchmark tests | 179 | **ALL must pass** (uses FakeVectorStore, not Qdrant) |
| RAG tests (non-Qdrant) | 54 | **ALL must pass** (protocols, search, persistence, decay, config, e2e pipeline, search_nodes tool) |
| RAG Qdrant integration | 13 | **Replace with Neo4j integration tests** (1:1 mapping) |
| API tests | 28 | **ALL must pass** |
| Pipeline tests | 12 | **ALL must pass** |
| Core tests | 7 | **ALL must pass** |

**Net test count:** 552 - 13 (Qdrant integration removed) + ≥15 (Neo4j integration added) + ≥12 (graph-specific new tests) = **≥ 566 tests**

**Pass/Fail:** HARD gate. Zero regressions in non-Qdrant tests. Qdrant integration tests must be replaced 1:1.

### 3.2 Benchmark Grade Maintenance

| Scenario | Current Grade | Minimum Post-Migration |
|----------|-------------|----------------------|
| Iran Escalation | B (≥0.70) | **B (≥0.70)** |
| Fed Rate Decision | B (≥0.70) | **B (≥0.70)** |

The benchmark scoring weights are:
- checkpoint_hit_rate: 25%, match_accuracy: 20%, reasoning_correctness: 20%, reasoning_completeness: 15%, match_quality: 10%, depth_appropriateness: 10%

The graph migration should not affect Pass 1 scores (checkpoint scanning, match scanning — these are trace-based, not search-based). Pass 2 (LLM judge) is also trace-based. The only indirect impact is if graph-powered search_nodes tool returns different results that change agent reasoning quality.

**Pass/Fail:** HARD gate. Run both scenarios post-migration. Grade must be ≥ B.

### 3.3 API Contract Stability

| Endpoint | Contract |
|----------|---------|
| All frontend-facing endpoints | **Response shape unchanged** — frontend must work without modification |
| SearchNodesTool interface | Input schema (`SearchNodesInput`) unchanged — agents use this tool |
| FetchNewsTool interface | No changes (not RAG-dependent) |

**Pass/Fail:** HARD gate. Verified by existing API tests + manual E2E.

---

## Gate 4: Code Quality

### 4.1 Protocol-Based DI

| Requirement | Details |
|-------------|---------|
| New `GraphStore` protocol | Must be defined in `backend/src/rag/protocols.py` alongside existing protocols |
| `FakeGraphStore` for tests | In-memory implementation in `backend/src/rag/fakes.py`, no Neo4j required |
| Existing protocols preserved | `VectorStore` protocol can be removed ONLY after all references are migrated |
| DI wiring | `dependencies.py` must wire `GraphStore` the same way it wires `VectorStore` today — lazy imports, init function |

**Pass/Fail:** HARD gate. `isinstance(FakeGraphStore(), GraphStore)` must return True (runtime_checkable).

### 4.2 Test Coverage

| Component | Minimum Coverage |
|-----------|-----------------|
| GraphStore protocol + implementation | **≥ 90%** line coverage |
| Graph search service | **≥ 85%** line coverage |
| Graph persistence (dual-write) | **≥ 85%** line coverage |
| Graph tools (new) | **≥ 80%** line coverage |
| FakeGraphStore | **100%** (it's test infrastructure) |

**Pass/Fail:** SOFT gate — document actual coverage, flag if below threshold.

### 4.3 Architectural Rules

| Rule | Verification |
|------|-------------|
| No hardcoded Neo4j URLs | Grep for `bolt://` or `neo4j://` outside config files |
| Clean MongoDB/Neo4j separation | MongoDB = metadata/state, Neo4j = relationships/search. No mixed queries. |
| No workarounds | No `# TODO`, `# HACK`, `# WORKAROUND` in new code |
| Lazy imports maintained | Neo4j/Graphiti imports inside `init_*()` functions, not module-level |
| No mock suppression | Tests use FakeGraphStore, not `@mock.patch` on Neo4j client |

**Pass/Fail:** HARD gate (all rules). Verified by grep + code review agent.

---

## Gate 5: Integration Test Scenarios

### 5.1 News → Graph → Search Roundtrip

**Setup:** Persist 3 news nodes with known content.
**Action:** Search for one by semantic query.
**Verify:**
- Node found with correct content, metadata, and score
- Graph entity created for key entities in news (e.g., "Federal Reserve")
- Relationships between entities stored as edges
- `session_id` exclusion filter works

### 5.2 Thinking → Effect → Graph Reuse

**Setup:** Run a thinking layer that produces effect nodes. Persist them.
**Action:** In a NEW session, search for effects from the prior session.
**Verify:**
- Cross-session search returns prior effects
- Decay scoring applied correctly (newer effects score higher)
- Graph traversal can follow causal chain (news → effect)

### 5.3 Temporal Supersession

**Setup:** Persist two versions of the same entity analysis (e.g., "NVIDIA outlook" from March 20 and March 25).
**Action:** Search with `date_from="2026-03-24"`.
**Verify:**
- Only the March 25 version returned
- Older version's `invalid_at` set correctly (if using Graphiti temporal model)
- Graph edges reflect the temporal relationship

### 5.4 Cross-Session Knowledge Reuse

**Setup:** Session A persists: news → effect_1 → opportunity_1. Session B starts.
**Action:** Session B agent uses `search_nodes` tool.
**Verify:**
- Session B finds Session A's analysis
- Graph provides richer context than flat search (shows causal chain)
- Session B's own nodes excluded from results

### 5.5 Graph Tool Chaining Patterns (NEW tools)

These test the tiered graph tools mentioned in Task #6:

| Tool Pattern | Test |
|-------------|------|
| **Drill-down** | Search "Fed rate impact" → get entity → traverse to connected effects |
| **Connection discovery** | Given two entities ("NVIDIA", "China tariffs"), find connecting paths |
| **Temporal comparison** | Compare entity state at two time points |
| **Neighborhood exploration** | Given one effect node, find all related entities within 2 hops |

Each pattern: verify correct results, verify no false connections, verify latency within Gate 2 targets.

### 5.6 Reconciliation & Pruning

**Setup:** Simulate a failed graph write (MongoDB succeeds, graph write fails).
**Action:** Run `reconcile()`.
**Verify:**
- Unindexed node is re-indexed to graph
- `indexed` flag updated in MongoDB
- No duplicate entities/edges created

**Setup:** Persist nodes with `created_at` > 90 days ago.
**Action:** Run `prune()`.
**Verify:**
- Nodes removed from both MongoDB and graph store
- Associated edges cleaned up (no orphan edges)

---

## Gate 6: Acceptance Criteria (Binary Pass/Fail)

### HARD Gates (ALL must pass — migration is blocked if any fails)

| # | Gate | Pass Condition |
|---|------|---------------|
| H1 | NDCG@20 ≥ 0.55 | `test_search_quality.py::test_ndcg_at_20` passes |
| H2 | Recall@20 ≥ 0.90 | `test_search_quality.py::test_recall_at_20` passes |
| H3 | MRR ≥ 0.50 | `test_search_quality.py::test_mrr` passes |
| H4 | Entity resolution ≥ 0.85 | New `test_entity_resolution` passes |
| H5 | Temporal filtering ≥ 0.95 | New `test_temporal_filtering` passes |
| H6 | User-facing write latency ≤ 50ms p95 | New `test_write_latency` passes |
| H7 | Simple search latency ≤ 500ms p95 | New `test_search_latency` passes |
| H8 | Non-Qdrant tests pass (539) | `pytest -m "not integration"` — 0 failures |
| H9 | Qdrant integration replaced 1:1 | ≥ 13 Neo4j integration tests pass |
| H10 | Benchmark grade ≥ B (both scenarios) | `test_benchmark.py` — both scenarios grade ≥ B |
| H11 | API contract unchanged | All API tests pass, no response shape changes |
| H12 | GraphStore protocol with FakeGraphStore | `isinstance(FakeGraphStore(), GraphStore)` is True |
| H13 | No architectural violations | Grep verification passes (no hardcoded URLs, no mixed queries, lazy imports) |

### SOFT Gates (failure triggers review, documented with justification)

| # | Gate | Pass Condition |
|---|------|---------------|
| S1 | Path discovery ≥ 0.80 | New test — review if below |
| S2 | Edge type correctness ≥ 0.90 | New test — review if below |
| S3 | Background write ≤ 2s p95 | Benchmark — document actual |
| S4 | Traversal search ≤ 1.5s p95 | Benchmark — document actual |
| S5 | Neo4j memory ≤ 2GB | docker stats — document actual |
| S6 | Graph code coverage ≥ 85% | pytest-cov — document actual |
| S7 | Net test count ≥ 566 | pytest --collect-only count |

### Definition of "Done"

The migration is **DONE** when:
1. All 13 HARD gates pass with evidence (test output, benchmark reports)
2. All SOFT gates are evaluated with documented values
3. SOFT gate failures have written justification and remediation plan
4. PR created with summary referencing this quality gates document
5. Code review agent confirms architectural compliance

---

## Qdrant-Specific Test Inventory (to be replaced)

These 13 tests in `backend/tests/rag/test_qdrant_integration.py` must be replaced with Neo4j equivalents:

1. `test_ensure_collection_creates_collection` → `test_ensure_graph_schema`
2. `test_ensure_collection_idempotent` → `test_ensure_graph_schema_idempotent`
3. `test_upsert_and_retrieve` → `test_add_episode_and_search`
4. `test_upsert_multiple_points` → `test_add_multiple_episodes`
5. `test_write_then_search_immediate` → `test_write_then_search_immediate`
6. `test_filter_by_node_type` → `test_filter_by_entity_type`
7. `test_filter_by_min_confidence` → `test_filter_by_min_confidence`
8. `test_filter_by_market` → `test_filter_by_market`
9. `test_exclude_session_id` → `test_exclude_session_id`
10. `test_combined_filters` → `test_combined_filters`
11. `test_delete_removes_point` → `test_delete_removes_entity`
12. `test_delete_empty_ids_is_noop` → `test_delete_empty_ids_is_noop`
13. `test_rrf_fusion_returns_scored_results` → `test_graph_search_returns_scored_results`

---

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Graphiti entity resolution is too aggressive (merges distinct entities) | False relationships, wrong search results | Tune entity resolution thresholds; golden set test catches this at Gate 1.2 |
| Neo4j cold start is slow | Startup time exceeds 10s gate | Warmup query in init; document actual timing |
| Graph traversal latency spikes under load | Agent tool becomes unusable | Limit traversal depth to 2 hops; cache hot paths |
| SiliconFlow embeddings + Graphiti compatibility | Integration failures | Task #1 validates this specifically |
| Dual-write to MongoDB + Neo4j doubles failure surface | Data inconsistency | Same reconciliation pattern as current Qdrant dual-write |
