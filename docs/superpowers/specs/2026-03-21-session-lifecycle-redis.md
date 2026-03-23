# Session Lifecycle & Redis Caching

**Parent:** [Design Spec](2026-03-21-session-lifecycle-pool-entities-design.md)

## Session States

Maps to existing `SessionStatus` enum in `models/thinking.py`:

```
Session status (MongoDB):  IDLE → PAUSED ↔ THINKING → COMPLETE | ERROR
Cache state (Redis):       hot (in Redis)  →  cold (Redis TTL expired, MongoDB only)
```

- **IDLE** — `POST /thinking` inserts to MongoDB, writes to Redis. Session created.
- **PAUSED/THINKING** — user stepping through. Hot in Redis.
- **COMPLETE** — `/match` done. Stays in Redis for cooldown (configurable, default 30 min).
- **ERROR** — exception occurred. Cache explicitly invalidated via `delete`.
- **cold** — not a session status. Means Redis TTL expired. Lazy-loaded back on revisit.

## Write-Aside Pattern

```
Write path:
  1. Write to MongoDB (source of truth)
  2. Write to Redis (hot cache)
  → Redis write failure is non-fatal — next read repopulates

Read path:
  1. Check Redis
  2. Miss? Load from MongoDB → write to Redis with TTL
  3. Return

Invalidation:
  1. On ERROR status → explicitly delete all session keys from Redis
  2. On TTL expiry → automatic (Redis handles it)
```

Requires adding `delete(key)` to `RedisClient` (currently only has `get`/`set`).

## Concurrency Guard

Add a `version` field to `ThinkingSession` model. The `/step` endpoint uses compare-and-swap:

```python
session = await col.find_one_and_update(
    {"id": session_id, "status": "paused", "version": expected_version},
    {"$set": {"status": "thinking", "version": expected_version + 1}},
    return_document=ReturnDocument.AFTER,
)
if not session:
    raise HTTPException(409, "Session modified by another request")
```

Redis meta key includes `version` for cache consistency — reads check version matches before using cached data.

## Redis Key Design

Split by access pattern — not one giant blob:

```
session:{id}:meta    → {status, current_layer, version, date, market}  TTL: 30min
session:{id}:nodes   → serialized nodes array                          TTL: 30min
session:{id}:edges   → serialized edges array                          TTL: 30min
```

SSE `/events` only reads `:meta` (tiny). `/step` reads `:nodes` + `:edges`. No endpoint needs everything.

## Model Integration

`SessionCache` service takes/returns `ThinkingSession` Pydantic model (and sub-components). Serialization to/from Redis is internal to the service — API layer never touches raw Redis keys.

## Pool References (No More Embedding)

Sessions store `{pool_date, pool_market}` instead of copying full pools. Pools fetched separately when needed from `news_entities` / `value_entities` collections.

### Migration (Backward Compatibility)

- **New sessions** — use `{pool_date, pool_market}` references. No embedded pools.
- **Existing sessions** — if `news_pool` / `value_pool` fields exist in the document, use them (legacy path). Compatibility check in repo layer: `session.get("news_pool") or await fetch_pool_entities(session["pool_date"], session["pool_market"])`.
- **`/step` endpoint** — updated to fetch pool entities on-demand using the reference. The entity set is resolved at step time, not session creation time.
- **Switchover** — happens in implementation step 7 (API updates). Steps 1-6 work with both old and new formats via the compatibility layer.
- **Snapshot concern** — pool entities may change between session steps (cron runs). This is intentional: the user sees the freshest data at each step. If snapshot-at-creation is needed later, add `pool_snapshot_ids[]` to the session.

## Session Persistence

- MongoDB keeps all sessions forever (audit trail)
- Redis only caches active sessions (auto-expires via TTL)
- `GET /api/thinking/{id}` — Redis first, fallback MongoDB (lazy load back into cache)
- Future: `GET /api/thinking/history?market=US` — query MongoDB for past sessions
