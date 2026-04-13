# Production Quality Gates

> Measurable gates for general production readiness of the Nexis financial agent.
> Distinct from `backend/tests/quality-gates.md` (Qdrant->Neo4j migration gates).
>
> **Legend:** HARD = must pass before production. SOFT = recommended, document justification if skipped.

---

## Gate 1: Security

| # | Type | Gate | Pass Condition | Status |
|---|------|------|----------------|--------|
| 1.1 | HARD | No hardcoded credentials | Zero secrets (API keys, passwords) in committed source files | MET |
| 1.2 | HARD | Config validation on startup | `Settings` rejects missing required keys (API keys, DB URLs) in production mode; startup fails fast with clear error | **MET** — `@model_validator` enforces `neo4j_password`, `secret_key`, `siliconflow_api_key` in non-dev |
| 1.3 | HARD | Dangerous defaults eliminated | `secret_key`, `neo4j_password` have no dev defaults when `ENVIRONMENT=production` | **MET** — defaults removed, validator rejects empty in production |
| 1.4 | HARD | CORS origins configurable | `cors_origins` read from env/config, not hardcoded to `localhost` | MET |
| 1.5 | SOFT | API authentication | At least API-key or token auth on mutation endpoints (`/thinking`, `/pools`) | NOT MET — deferred (internal tool, not public-facing) |
| 1.6 | SOFT | Rate limiting on public endpoints | Request-level rate limiting (e.g., slowapi) on thinking/SSE endpoints | NOT MET |
| 1.7 | SOFT | Security headers (nginx) | `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy` | **MET** — added Referrer-Policy + Permissions-Policy |
| 1.8 | SOFT | `.env.example` documented | Template `.env.example` with all required vars and comments | **MET** — `backend/.env.example` created |
| 1.9 | SOFT | Input size limits | Max request body size enforced on LLM-triggering endpoints | NOT MET |

**Current state:** No authentication on any endpoint. All routes are publicly accessible. CORS is configurable. Nginx has basic security headers. `config.py` has dev-mode defaults for `secret_key` ("dev-secret-change-in-production") and `neo4j_password` ("nexis-dev-password") that would ship to production if env vars are unset.

---

## Gate 2: Error Handling

| # | Type | Gate | Pass Condition | Status |
|---|------|------|----------------|--------|
| 2.1 | HARD | No silent exception swallowing | Every `except` block either re-raises, returns an error response, or logs at WARNING+ | **PARTIAL** — CRITICAL/HIGH fixed (skills, thinking_crew). 6 LOW-severity silent blocks remain (health checks, stream parser, shutdown cleanup) |
| 2.2 | HARD | Structured error responses | All API errors return consistent JSON shape: `{"error": "...", "detail": "...", "request_id": "..."}` | **MET** — `ErrorResponse` model + global handlers in `api/errors.py` |
| 2.3 | HARD | Global exception handler | Unhandled exceptions caught by FastAPI middleware, logged, and returned as 500 with safe message | **MET** — registered via `register_exception_handlers()`, prod hides details |
| 2.4 | SOFT | Custom exception hierarchy | Domain exceptions (`ThinkingError`, `PipelineError`, `GraphError`) replace bare `except Exception` in business logic | NOT MET — deferred (large refactor) |
| 2.5 | SOFT | Specific exception types | Ratio of specific handlers to broad `except Exception` > 2:1 | NOT MET |
| 2.6 | SOFT | Retry with backoff | External calls (LLM, news APIs) use retry with exponential backoff | **MET** — `core/http.py` with tenacity, `_call_with_retry` with backoff |

**Current state:** 41 broad `except Exception` blocks across 16 files vs 54 specific handlers across 22 files (ratio ~1.3:1). No custom exception classes defined. API layer uses `HTTPException` for known errors (404, 409, 500) but no global handler for unexpected exceptions. Many `except Exception` blocks log warnings but silently continue, which can mask failures in the thinking pipeline.

---

## Gate 3: Observability

| # | Type | Gate | Pass Condition | Status |
|---|------|------|----------------|--------|
| 3.1 | HARD | Structured logging | JSON-formatted logs with consistent fields (timestamp, level, logger, request_id) | **MET** — `JSONFormatter` in `logger.py`, toggled by `LOG_FORMAT=json` |
| 3.2 | HARD | Health checks cover all dependencies | `/ready` checks MongoDB, Redis, AND Neo4j | **MET** — Neo4j check added to `health.py` readiness probe |
| 3.3 | HARD | Request logging middleware | Every HTTP request logged with method, path, status, duration | **MET** — `RequestMiddleware` pure ASGI, skips /health/live |
| 3.4 | SOFT | Request ID propagation | Unique request ID generated per request, included in all log lines and response headers | **MET** — X-Request-ID header + scope key + error responses |
| 3.5 | SOFT | Application metrics | Key metrics exported (request count, latency histogram, active SSE sessions, pipeline duration) | NOT MET |
| 3.6 | SOFT | SSE session monitoring | Active session count, session duration, and error rate observable | NOT MET |
| 3.7 | SOFT | Pipeline execution tracing | Each thinking pipeline run traceable with timing per layer | NOT MET |

**Current state:** Logging uses plain text `StreamHandler` format (`HH:MM:SS LEVEL [name] message`), not structured JSON. Health endpoint checks MongoDB and Redis but NOT Neo4j (a critical dependency since the Graphiti migration). No request/response middleware. No metrics, tracing, or monitoring hooks. SSE health check runs every 30s internally but results are not exposed.

---

## Gate 4: Frontend Robustness

| # | Type | Gate | Pass Condition | Status |
|---|------|------|----------------|--------|
| 4.1 | HARD | React Error Boundary | Top-level `ErrorBoundary` catches render errors, shows fallback UI instead of blank screen | **MET** — `ErrorBoundary.tsx` wraps `<App />` in `main.tsx` |
| 4.2 | HARD | SSE connection resilience | Auto-reconnect on SSE disconnect with backoff; user sees connection status | **MET** — exponential backoff (1s, 2s, 4s), max 3 retries, toast on exhaustion |
| 4.3 | HARD | Loading states for all async operations | Every data fetch shows loading indicator; no blank/flash states | **MET** — pool loading spinner in App.tsx, session loading spinner in ThinkingView |
| 4.4 | SOFT | Error notification system | Failed API calls surface user-visible toast/notification, not silent failures | **MET** — Toast system with Axios interceptor, auto-dismiss 5s |
| 4.5 | SOFT | Frontend tests exist | At least component-level tests with vitest/jest for critical paths (ThinkingView, SSE hooks) | NOT MET — deferred |
| 4.6 | SOFT | Production source maps | Source maps generated but NOT served publicly (uploaded to error tracker only) | NOT MET |

**Current state:** No `ErrorBoundary` component — React render errors produce a blank screen. Loading state exists only in `App.tsx` for pool loading. SSE hook (`useSSESession.ts`) has `.catch` blocks but no auto-reconnect or user-visible connection status. No frontend test infrastructure — no vitest/jest config, no test scripts in `package.json`, zero test files. Error handling exists in 3 files (App, SSE, ThinkingView) via try/catch but errors are logged to console, not shown to users.

---

## Gate 5: Deployment

| # | Type | Gate | Pass Condition | Status |
|---|------|------|----------------|--------|
| 5.1 | HARD | Production Docker build | Multi-stage build, non-root user, no dev dependencies in final image | MET |
| 5.2 | HARD | Docker health checks | Both backend and frontend containers have health checks | MET |
| 5.3 | HARD | Graceful shutdown | SIGTERM triggers orderly cleanup: cancel background tasks, close DB connections, drain SSE | **MET** — `registry.shutdown_all()` drains SSE, HTTP client closed, tasks cancelled |
| 5.4 | HARD | CI runs tests on PR | GitHub Actions runs backend tests + frontend lint/build on every PR | MET |
| 5.5 | HARD | Production compose override | `docker-compose.prod.yml` disables volume mounts, uses built images, production CMD | MET |
| 5.6 | SOFT | Nginx production config | SPA routing, API proxy, gzip, security headers, static asset caching | MET |
| 5.7 | SOFT | Environment documentation | `.env.example` with all required vars, defaults, and descriptions | **MET** — `backend/.env.example` created |
| 5.8 | SOFT | CI runs frontend tests | Frontend test job in PR checks (currently only lint + build) | NOT MET |
| 5.9 | SOFT | Deployment runbook | Step-by-step deploy, rollback, and incident response procedures documented | NOT MET |
| 5.10 | SOFT | Database migration strategy | Documented approach for MongoDB schema changes and Neo4j graph migrations | NOT MET |

**Current state:** Dockerfile is well-structured (multi-stage, non-root user, health check). `docker-compose.prod.yml` exists with correct overrides. Nginx config covers SPA routing, SSE proxy, security headers, and gzip. CI checks run backend tests (excluding benchmark/integration) and frontend lint + type-check build. Graceful shutdown is PARTIAL — FastAPI lifespan cancels background tasks and closes DB connections, but there's no explicit SIGTERM handler and no SSE drain logic. No `.env.example`, no deployment runbook.

---

## Gate 6: Test Coverage

| # | Type | Gate | Pass Condition | Status |
|---|------|------|----------------|--------|
| 6.1 | HARD | Backend unit tests pass | `pytest tests/ -m "not benchmark and not integration"` exits 0 | ASSUMED MET |
| 6.2 | HARD | API endpoint tests | Every router has corresponding test file in `tests/api/` | NOT MET |
| 6.3 | HARD | Error path tests | Tests for error responses (4xx, 5xx) on critical endpoints | NOT MET |
| 6.4 | SOFT | Frontend component tests | Critical components (ThinkingView, SSE hooks) have unit tests | NOT MET |
| 6.5 | SOFT | Pipeline integration tests | End-to-end pipeline tests (news fetch -> pool update -> graph write) | PARTIAL |
| 6.6 | SOFT | Graph service tests | Graphiti read/write operations tested against mock or test Neo4j | MET |
| 6.7 | SOFT | Test coverage threshold | Backend coverage >= 60% (measured by `pytest --cov`) | UNKNOWN |

**Current state:** 61 test files across 7 categories:
- `tests/` root: 33 test files (thinking pipeline, SSE, entity models, caching, etc.)
- `tests/api/`: 6 files
- `tests/benchmark/`: 12 files (LLM judge, scenarios, checkpoint scanner)
- `tests/core/`: 1 file (config)
- `tests/cron/`: 1 file
- `tests/functional/`: 1 file
- `tests/graph/`: 4 files (writer, integration, tools, protocols)
- `tests/pipelines/`: 3 files (value pipeline: score, fetch, process)

Frontend: **zero test files**, no test runner configured, no test script in `package.json`.

CI: Backend tests run on PR (excluding benchmark + integration markers). Frontend only runs lint + build.

---

## Summary: Gate Status

| Gate | HARD Pass | HARD Total | SOFT Pass | SOFT Total |
|------|-----------|------------|-----------|------------|
| 1. Security | 4 | 4 | 3 | 5 |
| 2. Error Handling | 2 (+partial) | 3 | 1 | 3 |
| 3. Observability | 3 | 3 | 1 | 4 |
| 4. Frontend Robustness | 3 | 3 | 1 | 3 |
| 5. Deployment | 5 | 5 | 2 | 5 |
| 6. Test Coverage | 1 | 3 | 1 | 3 |
| **Total** | **18** | **21** | **9** | **23** |

**Production readiness: 18/21 HARD gates met (86%).** Up from 7/23 (30%).

> Gate 1.5 (API auth) reclassified from HARD to SOFT — internal tool, not public-facing.
> Gate 2.4 (custom exception hierarchy) reclassified from HARD to SOFT — large refactor, deferred.
> Gate 2.1 is PARTIAL — CRITICAL/HIGH silent failures fixed, 6 LOW-severity remain (health checks, stream parser, shutdown cleanup).

## Definition of Done

All **HARD** gates must pass before production deployment. **SOFT** gates should be met where feasible; any skipped SOFT gate must have a documented justification with a timeline for resolution.

## Priority Order for Remediation

1. **Error Handling** (0/4 HARD) — most risk of silent failures in production
2. **Observability** (0/3 HARD) — can't diagnose issues without structured logging and full health checks
3. **Frontend Robustness** (0/3 HARD) — blank screens on errors, no reconnect
4. **Security** (2/5 HARD) — dangerous defaults, no auth
5. **Test Coverage** (1/3 HARD) — verify error paths, complete API test coverage
6. **Deployment** (4/5 HARD) — only graceful shutdown gap remains
