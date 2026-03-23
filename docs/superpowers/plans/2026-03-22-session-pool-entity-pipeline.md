# Session Lifecycle & Pool Entity Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic session document with Redis-cached split keys and transform raw pool dumps into owned entities with cron-driven lifecycle management.

**Architecture:** Write-aside caching (MongoDB truth + Redis hot cache), Strategy Pattern for pluggable pool pipelines (fetch → process → score → retain), cron-driven ingestion with hybrid dedup.

**Tech Stack:** FastAPI, Motor (MongoDB async), redis.asyncio, Pydantic v2, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-21-session-lifecycle-pool-entities-design.md` + 3 sub-specs

---

## Key Workflows (E2E Verification Map)

### Workflow 1: Session Hot Path
```
User starts session → Redis populated → /step reads from Redis →
/toggle updates both stores → /match completes → Redis TTL → cold in MongoDB →
User revisits → lazy-load back to Redis
```
**Verify:** Start session, step twice, toggle a node, match. Check Redis keys exist. Wait for TTL (or manually expire). GET session — should reload from MongoDB into Redis.

### Workflow 2: News Entity Lifecycle
```
Cron fetches news → extract entities → embed → hybrid dedup against existing →
merge (add source) or insert (new entity) → score (decay function) → persist →
re-score existing (freshness decays) → stale entities filtered from new sessions
```
**Verify:** Insert 3 news entities. Run pipeline with 1 duplicate + 1 new. Assert: duplicate merged (source count=2), new inserted, old entity re-scored with lower freshness.

### Workflow 3: Value Entity Lifecycle
```
Cron fetches fundamentals → upsert by ticker → score (bounce-back) → persist →
stale entities filtered
```
**Verify:** Insert value entity. Run pipeline with updated price. Assert: same entity updated (not duplicated), score recalculated.

### Workflow 4: Strategy Swap
```
Replace AlphaVantageNewsFetch with MockNewsFetch →
pipeline produces same output shape → no pipeline code changes
```
**Verify:** Run pipeline with mock strategy. Assert: PipelineResult has correct counts, entities persisted.

---

## File Structure

### New Files (16)
```
backend/src/
├── models/
│   ├── news_entity.py, value_entity.py, pool_common.py
├── database/repositories/
│   ├── news_entity_repo.py, value_entity_repo.py
├── services/
│   └── session_cache.py
├── pipelines/
│   ├── base.py
│   ├── news/ (fetch.py, process.py, score.py)
│   └── value/ (fetch.py, process.py, score.py)
└── cron/
    └── scheduler.py
```

### Modified Files (5)
```
backend/src/database/redis.py, core/config.py, models/thinking.py,
api/thinking.py, api/pools.py
```

---

## Tasks (execute in order)

| # | Task | Files | Plan |
|---|------|-------|------|
| 1 | [Redis Client + Session Cache](session-pool-pipeline/task-1-session-cache.md) | redis.py, session_cache.py, config.py | Write-aside cache with split keys |
| 2 | [Entity Models + Repos](session-pool-pipeline/task-2-entity-models.md) | news_entity.py, value_entity.py, repos | Pydantic models + MongoDB repos |
| 3 | [Pipeline Base](session-pool-pipeline/task-3-pipeline-base.md) | pipelines/base.py | PoolPipeline orchestrator + ThresholdRetain |
| 4 | [News Pipeline](session-pool-pipeline/task-4-news-pipeline.md) | pipelines/news/* | Decay score, hybrid dedup, fetch placeholder |
| 5 | [Value Pipeline](session-pool-pipeline/task-5-value-pipeline.md) | pipelines/value/* | Bounce-back score, ticker upsert |
| 6 | [Cron Scheduler](session-pool-pipeline/task-6-cron.md) | cron/scheduler.py, config.py | Pipeline wiring + job registration |
| 7a | [Redis Lifespan + CAS Guard](session-pool-pipeline/task-7a-lifespan-and-cas.md) | main.py, thinking.py | Redis lifespan, CAS guard on /step |
| 7b | [Pools Entity Endpoint](session-pool-pipeline/task-7b-pools-entity-endpoint.md) | pools.py | Entity-based response, stale filtering, legacy fallback |

## E2E Verification

See [E2E Verification Checklist](session-pool-pipeline/e2e-verification.md)
