# Macro News Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Broaden the news pool to include macro/geopolitical news by adding multi-source fetch (Perigon `/stories` + NewsAPI), fixing scoring to incentivize macro news, removing market partition on news, and giving the Thinker agent a `fetch_news` tool for directed search.

**Architecture:** Three fetch modes (cron stories, cron broad, agent on-demand) feed a single global `news_entities` collection. Scoring uses scope + cluster factors instead of ticker relevance. A 40% tiered quota guarantees macro news representation. The agent can actively pull news mid-reasoning via a new tool.

**Tech Stack:** Python, FastAPI, Motor (MongoDB async), httpx, CrewAI, Perigon API, NewsAPI

**Spec:** `docs/superpowers/specs/2026-03-24-macro-news-pipeline-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/src/models/news_entity.py` | Modify | Add `scope`, `origin`, `story_cluster_size`; remove `market` |
| `backend/src/models/pool_common.py` | Modify | Make `FetchStrategy.fetch()` accept optional market |
| `backend/src/pipelines/base.py` | Modify | Make `market` optional in `PoolPipeline` |
| `backend/src/pipelines/news/score.py` | Modify | New formula: scope_factor + cluster_factor |
| `backend/src/pipelines/news/process.py` | Modify | Remove `market` from `_gen_id` hash |
| `backend/src/pipelines/news/fetch.py` | Rewrite | `PerigonStoriesFetch`, `PerigonAllFetch`, `NewsAPIHeadlinesFetch`, `CompositeFetch` |
| `backend/src/pipelines/news/quota.py` | Create | Tiered quota enforcement |
| `backend/src/services/newsapi.py` | Create | NewsAPI client with caching + keyword-based classification |
| `backend/src/services/perigon.py` | Modify | Add `fetch_perigon_stories()`, broaden categories |
| `backend/src/agents/tools/__init__.py` | Create | Package init |
| `backend/src/agents/tools/fetch_news.py` | Create | Agent tool for directed news search |
| `backend/src/agents/thinking_crew.py` | Modify | Register `FetchNewsTool` in Thinker agent |
| `backend/src/database/repositories/news_entity_repo.py` | Modify | Support `market=None` queries |
| `backend/src/api/pools.py` | Modify | Global news pool, market only for values |
| `backend/src/api/thinking.py` | Modify | Global news pool loading + tiered quota |
| `backend/src/cron/scheduler.py` | Modify | Single global news pipeline |
| `backend/src/core/config.py` | Modify | Add new config fields |

---

## Tasks

| # | Task | Files | Detail |
|---|------|-------|--------|
| 1 | Data Model + Config Changes | `news_entity.py`, `config.py` | [[tasks-1-3]] |
| 2 | Scoring Redesign | `score.py`, `test_news_pipeline.py` | [[tasks-1-3]] |
| 3 | Pipeline Infrastructure (market-optional) | `pool_common.py`, `base.py`, `process.py`, `news_entity_repo.py` | [[tasks-1-3]] |
| 4 | NewsAPI Client | `newsapi.py` (new) | [[tasks-4-6]] |
| 5 | Perigon Stories Fetch | `perigon.py` | [[tasks-4-6]] |
| 6 | Composite Fetch + Pipeline Wiring | `fetch.py`, `scheduler.py` | [[tasks-4-6]] |
| 7 | Agent `fetch_news` Tool | `tools/fetch_news.py` (new) | [[tasks-7-10]] |
| 8 | Thinker Agent Integration | `thinking_crew.py` | [[tasks-7-10]] |
| 9 | API Layer — Global Pool + Tiered Quota | `pools.py`, `thinking.py`, `quota.py` (new) | [[tasks-7-10]] |
| 10 | Integration Test + Full Verification | integration test | [[tasks-7-10]] |

**Dependency order:** Tasks 1-3 (foundation) → Tasks 4-6 (fetch sources) → Tasks 7-10 (integration)

**Parallelism:** Tasks 4 and 5 are independent. Tasks 7 and 9 are independent.
