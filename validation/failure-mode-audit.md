# Failure Mode Audit

## Summary

**46 except blocks** audited across 20 backend files.

| Severity | Count | Description |
|----------|-------|-------------|
| CRITICAL | 1 | User-facing silent failure — feature silently broken |
| HIGH | 4 | Agent failures return empty results with no user signal |
| MEDIUM | 22 | Degraded functionality, logged but not surfaced to user |
| LOW | 19 | Expected fallbacks, flow control, or cosmetic |

**Top-3 structural issues:**
1. No startup config validation — app boots but crashes on first LLM call if API key missing
2. Zero dual-write reconciliation — MongoDB and Neo4j can silently diverge forever
3. In-flight SSE sessions not drained on shutdown — clients hang, data may be lost

---

## Bare Exception Audit

### CRITICAL (1)

| File | Line | Catches | Logs? | Recommendation |
|------|------|---------|-------|----------------|
| `agents/skills/__init__.py` | 29 | Broken skill module import | **SILENT** (`pass`) | Log warning with module name + traceback. Broken skills are invisible to operators. |

### HIGH (4)

| File | Line | Catches | Logs? | Recommendation |
|------|------|---------|-------|----------------|
| `services/thinking_service.py` | 113 | Thinker agent failed at layer N | error | Returns empty LayerResult. User sees "no effects" with no explanation. Push structured error to SSE. |
| `services/thinking_service.py` | 403 | `run_layer_streaming` outer catch-all | error + SSE push | Good — pushes error event. But error message is raw exception string, may leak internals. Sanitize. |
| `agents/thinking_crew.py` | 191 | `run_thinker` complete failure | error | Returns `([], [], [], [], tokens)`. Caller gets empty data, no way to distinguish "no effects" from "crash". Add structured error return. |
| `agents/thinking_crew.py` | 383 | `run_matcher` complete failure | error | Returns `([], [], tokens)`. Same issue — no way to distinguish empty matches from crash. |

### MEDIUM (22)

| File | Line | Catches | Logs? | Recommendation |
|------|------|---------|-------|----------------|
| `main.py` | 35 | Startup news pipeline | warning | OK for startup. Consider retry with backoff. |
| `main.py` | 39 | Startup value pipeline | warning | Same as above. |
| `main.py` | 52 | Cron news pipeline | warning | Stale data risk. Add metric/alert hook. |
| `main.py` | 56 | Cron value pipeline | warning | Same as above. |
| `main.py` | 82 | Redis connection | warning | App runs without Redis — session caching silently disabled. Health endpoint reports it. |
| `services/thinking_service.py` | 75 | `_call_with_retry` per-attempt | warning on retry | Good — retries. But generic `except Exception` catches CancelledError too (should let it propagate). |
| `services/thinking_service.py` | 135 | Matcher failed (batch) | warning | Continues without matches. Acceptable degradation, but user sees no signal. |
| `services/thinking_service.py` | 152 | Controller failed (batch) | warning | Uses default continue/stop logic. Good fallback, but should surface. |
| `services/thinking_service.py` | 348 | Matcher failed (streaming) | warning | Same as batch matcher. |
| `services/thinking_service.py` | 365 | Controller failed (streaming) | warning | Same as batch controller. |
| `services/stream_parser.py` | 95 | `_extract_effects` JSON repair | **SILENT** (`pass`) | Returns None, triggers partial delta path. Expected for incremental parsing, but should log at debug level. |
| `services/stream_parser.py` | 134 | `_emit_partial_deltas` JSON repair | **SILENT** (`pass`) | Same — expected but should log at debug. |
| `services/perigon.py` | 279 | `fetch_perigon_news` HTTP/parse | error, returns [] | Caller gets empty list — indistinguishable from "no news found". |
| `services/perigon.py` | 403 | `fetch_perigon_stories` HTTP/parse | error, returns [] | Same issue. |
| `services/newsapi.py` | 208 | `fetch_newsapi_headlines` HTTP/parse | error, returns [] | Same pattern. |
| `services/newsapi.py` | 265 | `fetch_newsapi_everything` HTTP/parse | error, returns [] | Same pattern. |
| `services/data_sources.py` | 91 | Alpha Vantage HTTP fail | error, returns [] | Same — empty list hides error from caller. |
| `services/data_sources.py` | 178 | yfinance outer catch | error, returns [] | Same. |
| `cron/scheduler.py` | 140 | News pipeline run | error + MongoDB record | Good — error is persisted in `pipeline_runs`. |
| `cron/scheduler.py` | 209 | Value pipeline per-market | error + MongoDB record | Good — same as above. |
| `pipelines/news/fetch.py` | 22 | CompositeFetch per-fetcher | warning | One source fails, others continue. Acceptable. |
| `api/thinking.py` | 268 | `think_step` full failure | error + 500 response | Sets session status to "error". Exposes raw exception in detail — potential info leak. |

### LOW (19)

| File | Line | Catches | Logs? | Notes |
|------|------|---------|-------|-------|
| `main.py` | 91 | Graph init failed | warning | Graph is optional, expected. |
| `main.py` | 114 | `close_graph_services` on shutdown | **SILENT** | Shutdown cleanup — acceptable but could mask resource leak. |
| `graph/writer.py` | 45 | `ingest_news_article` | warning + exc_info | Fire-and-forget, expected. |
| `graph/writer.py` | 88 | `ingest_thinking_node` | warning + exc_info | Same. |
| `graph/writer.py` | 123 | `try_ingest_thinking_layer` RuntimeError | **SILENT** | Expected — graph not initialized. |
| `graph/writer.py` | 135 | `try_ingest_news_batch` RuntimeError | **SILENT** | Same. |
| `graph/writer.py` | 145 | `fire_and_forget` wrapper | warning + exc_info | Background task, acceptable. |
| `graph/writer.py` | 151 | No running event loop | warning | Expected edge case. |
| `services/thinking_service.py` | 26 | litellm ImportError | **SILENT** (sets None) | Optional dep, checked before use. |
| `services/data_sources.py` | 33 | Perigon fallback to Alpha Vantage | debug | Expected cascade. |
| `services/data_sources.py` | 100 | yfinance ImportError | warning | Missing optional dep. |
| `services/data_sources.py` | 167 | Per-ticker yfinance error | debug | Individual ticker failure, continues. |
| `database/redis.py` | 18 | Redis ping after connect | Re-raises | Proper — cleans up then propagates. |
| `api/health.py` | 32 | MongoDB health check | warning + exc_info | Health endpoint, expected. |
| `api/health.py` | 45 | Redis health check | warning + exc_info | Same. |
| `api/pools.py` | 81 | datetime ValueError | Returns False | Expected validation. |
| `agents/thinking_crew.py` | 127 | Graph store RuntimeError/ImportError | **SILENT** (fallback) | Falls back to no graph tools. Expected. |
| `agents/thinking_crew.py` | 583 | `run_controller` failure | error | Returns stop + error reasoning. Reasonable fallback. |
| `api/thinking_auto.py` | 200 | Auto pipeline outer catch | error + SSE push + DB update | Comprehensive handling. |

**Note:** 6 graph tool files (`graph_search.py`, `explore_entity.py`, `find_paths.py`, `get_relationships.py`, `raw_cypher.py`, `fetch_news.py`) each have `except RuntimeError:` for event loop detection. These are flow control, not error handling — all LOW.

---

## Config Gaps

### 1. No Startup Validation

`config.py` (Settings) uses pydantic-settings with all defaults. The app boots successfully even with **zero** configuration. Failures happen at runtime:

| Config | Default | When it fails | Impact |
|--------|---------|---------------|--------|
| `siliconflow_api_key` | `""` | First LLM call → `ValueError` in `_get_api_key()` | Every thinking session crashes |
| `perigon_api_key` | `""` | Never crashes — returns empty `[]` | Silent empty news pool |
| `newsapi_api_key` | `""` | Never crashes — returns empty `[]` | Silent empty headlines |
| `neo4j_password` | `"nexis-dev-password"` | Never — used as-is | Security risk in prod |
| `secret_key` | `"dev-secret-change-in-production"` | Never — used as-is | Security risk in prod |

**Recommendation:** Add a `validate_production_config()` that checks critical keys at startup and refuses to boot in production mode if they're missing.

### 2. Environment Field is Dead Code

`settings.environment` defaults to `"development"` but is **never referenced anywhere** in the backend. No code branches on it, no log enrichment uses it, no behavior changes.

### 3. Perigon API Key Bypass

`perigon.py:18` reads `PERIGON_API_KEY = os.environ.get("PERIGON_API_KEY", "")` directly from `os.environ`, ignoring `settings.perigon_api_key`. The `.env` file value loaded by pydantic-settings and the env var are usually the same, but this bypasses validation and creates two sources of truth.

### 4. Alpha Vantage Hardcoded Key

`data_sources.py:15-16` hardcodes a default Alpha Vantage API key (`IL2J1EVKMUH1PEJI`). This key is not in Settings — it's read directly from `os.environ`. Leaks a real API key in source code.

---

## Dual-Write Consistency

### Architecture

```
Request → MongoDB (blocking, await) → Graph/Neo4j (fire-and-forget, background task)
```

- Primary store: MongoDB (blocking writes in `thinking.py`, `thinking_auto.py`, `scheduler.py`)
- Secondary store: Neo4j via Graphiti (fire-and-forget via `writer.py:fire_and_forget()`)

### Failure Modes

| Scenario | What happens | Detection | Recovery |
|----------|-------------|-----------|----------|
| MongoDB write succeeds, graph write fails | Data in MongoDB only. `writer.py` logs warning. | Log search only | None — no retry, no reconciliation |
| Graph services not initialized | `try_ingest_*` catches RuntimeError, silent no-op | None | None — all data skipped |
| Background task cancelled | `fire_and_forget` wrapper catches Exception, logs warning | Log search only | None |
| Event loop not running | `fire_and_forget` logs warning, skips write | Log search only | None |

### Missing Mechanisms

1. **No `indexed` flag** — no way to know which MongoDB documents have been synced to Neo4j
2. **No reconciliation job** — no batch process to detect/fix divergence
3. **No retry** — fire-and-forget means exactly one attempt
4. **No metrics** — no counter of successful/failed graph writes
5. **No compensating transaction** — if graph write fails, MongoDB doesn't roll back

### Risk Assessment

**MEDIUM-HIGH** — Graph is currently used for "knowledge reuse" (agent tool lookups). If graph falls behind MongoDB, agents make decisions on stale/incomplete data. The fire-and-forget design is intentional (graceful degradation), but there's no mechanism to eventually converge.

---

## Graceful Shutdown

### What's Handled

```python
# main.py:104-117 — lifespan shutdown
for task in [health_task, cron_task, prepopulate_task]:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

await close_graph_services()  # wrapped in silent except Exception
await redis_client.close()
await mongodb.close()
```

- **Background tasks**: 3 tasks (`health_task`, `cron_task`, `prepopulate_task`) are properly cancelled
- **Graph**: closed with silent exception catch
- **Redis**: closed normally
- **MongoDB**: closed normally

### What's NOT Handled

1. **In-flight SSE sessions** — The `SessionRegistry` is **never drained on shutdown**. Active `_run_with_lifecycle` tasks from `thinking_auto.py` continue running until process kill:
   - Connected SSE clients receive no shutdown signal
   - Pipeline tasks may be mid-write to MongoDB when the connection closes
   - In-memory session queues are lost

2. **No SIGTERM handler** — No explicit signal handling. Relies on uvicorn's default SIGTERM → lifespan shutdown, which works but:
   - No grace period for in-flight requests
   - No drain signal to load balancers
   - SSE connections are not closed cleanly

3. **No close timeout** — `redis_client.close()` and `mongodb.close()` have no timeout. If a connection hangs, shutdown hangs indefinitely.

4. **Background graph writes** — Tasks created by `fire_and_forget()` via `loop.create_task()` are not tracked. During shutdown:
   - They're not cancelled (nobody holds a reference)
   - They race against `close_graph_services()` which closes the Neo4j connection
   - Could produce "connection closed" errors

### Risk Assessment

**HIGH** — In a container environment (Docker, k8s), SIGTERM + grace period is the normal shutdown path. Without SSE session draining:
- Users see hanging connections that never resolve
- Pipeline state may be inconsistent (written to queue but not MongoDB)
- Health checks pass during drain period when they shouldn't

---

## Appendix: Exception Pattern Summary

| Pattern | Count | Assessment |
|---------|-------|------------|
| `except Exception as e:` + `log.error/warning` + return empty | 18 | Most common. Swallows error from caller's perspective. |
| `except Exception:` + `pass` (truly silent) | 5 | Worst pattern. Broken skills, failed graph close, stream parser. |
| `except Exception:` + `log.warning(exc_info=True)` | 5 | Fire-and-forget writes. Acceptable for optional features. |
| `except Exception as e:` + push SSE error | 2 | Best pattern for streaming — user gets notified. |
| `except RuntimeError:` (flow control) | 8 | Event loop detection + graph init check. Not error handling. |
| `except (RuntimeError, ImportError):` (expected) | 2 | Optional dependency fallback. Acceptable. |
| `except ImportError:` | 2 | Missing optional packages. Logged. |
| `except ValueError:` | 1 | Expected validation. |
| `except asyncio.CancelledError: raise` | 1 | Correct pattern — re-raises. |
| `except asyncio.TimeoutError:` | 2 | Health check timeouts. Logged. |
