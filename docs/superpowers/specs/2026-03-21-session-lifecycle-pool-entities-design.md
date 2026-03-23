# Session Lifecycle & Pool Entity Management — Design Spec

**Date:** 2026-03-21
**Status:** Draft
**Scope:** Backend session caching, pool entity lifecycle, strategy abstraction, cron pipelines

## Problem Statement

1. **Session performance** — every API call loads the entire session document from MongoDB. No caching despite Redis being defined.
2. **Pool coupling** — pools are raw API dumps copied into each session. No dedup, scoring, or lifecycle.
3. **No extensibility** — fetch/score/retain logic is hardcoded.

## Design Goals

- Sessions persist permanently (audit trail) with Redis hot-caching for active sessions
- Pools become owned entities with lifecycle management (dedup, decay, retention)
- Strategy abstraction enables swapping logic without touching the pipeline
- Cron-driven ingestion to avoid API spikes

## Sub-Specs

- [Session Lifecycle & Redis Caching](2026-03-21-session-lifecycle-redis.md)
- [Pool Entity Management](2026-03-21-pool-entity-management.md)
- [Strategy Abstraction & File Layout](2026-03-21-strategy-abstraction-layout.md)

## Implementation Order

1. **Session caching** — Redis write-aside, split keys, update thinking API
2. **Entity models + repos** — NewsEntity, ValueEntity, new collections
3. **Pipeline base + strategies** — PoolPipeline orchestrator, strategy protocols
4. **News pipeline** — fetch, embed, hybrid dedup, decay scoring
5. **Value pipeline** — fetch, upsert, bounce-back scoring
6. **Cron integration** — scheduler, jobs, config
7. **API updates** — `?include_stale`, pool references, deprecate old `pools` collection
