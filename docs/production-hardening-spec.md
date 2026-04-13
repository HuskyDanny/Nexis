# Production Hardening Spec

> Nexis Financial Agent v2 — comprehensive audit of production gaps with specific file-level changes.
> Generated: 2026-04-13

---

## 1. Security Changes

### 1.1 Hardcoded Secrets (CRITICAL)

**`backend/src/core/config.py:16-17`** — Default values for `neo4j_password` and `secret_key` are dev credentials baked into source:
```python
neo4j_password: str = "nexis-dev-password"      # line 16
secret_key: str = "dev-secret-change-in-production"  # line 17
```
**Fix:** Remove default values. Use empty string defaults and add a startup validator that raises on missing required secrets when `ENVIRONMENT != "development"`:
```python
neo4j_password: str = ""
secret_key: str = ""

@model_validator(mode="after")
def _require_secrets_in_prod(self):
    if self.environment != "development":
        missing = []
        if not self.neo4j_password:
            missing.append("NEO4J_PASSWORD")
        if self.secret_key == "" or "dev" in self.secret_key:
            missing.append("SECRET_KEY")
        if not self.siliconflow_api_key:
            missing.append("SILICONFLOW_API_KEY")
        if missing:
            raise ValueError(f"Required secrets not set: {', '.join(missing)}")
    return self
```

**`backend/src/graph/config.py:13`** — Duplicate `neo4j_password: str = "nexis-dev-password"`.
**Fix:** Remove default value, same pattern as above. This config is always constructed from `settings` in `graph/dependencies.py:19-23`, so the value will come from the validated `Settings`.

**`backend/src/services/data_sources.py:15-17`** — **Hardcoded API key in source code**:
```python
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "IL2J1EVKMUH1PEJI")
```
**Fix:** Remove the hardcoded default. Use `settings.alpha_vantage_api_key` (add to `Settings`), default to empty string.

**`docker-compose.yml:24,76`** — Dev password in compose file:
```yaml
NEO4J_PASSWORD: nexis-dev-password   # line 24
NEO4J_AUTH: neo4j/nexis-dev-password  # line 76
```
**Fix:** Use `${NEO4J_PASSWORD}` variable substitution, populated from `.env` file.

**`backend/src/services/perigon.py:17`** — Reads `PERIGON_API_KEY` directly from `os.environ` instead of `settings`. Inconsistent with the rest of the codebase.
**Fix:** Use `settings.perigon_api_key` (already exists in config.py:21).

### 1.2 CORS Over-Permissive

**`backend/src/main.py:121-126`**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # OK — configurable
    allow_methods=["*"],    # Too broad — should be ["GET", "POST", "PATCH", "OPTIONS"]
    allow_headers=["*"],    # Too broad — should be ["Content-Type", "Authorization"]
)
```
**Fix:** Restrict `allow_methods` to actually-used HTTP methods and `allow_headers` to required headers. Add `allow_credentials=True` if auth cookies will be used.

### 1.3 MongoDB & Redis Without Auth

**`docker-compose.yml:44-50,56-63`** — MongoDB and Redis run with no authentication.
**Fix (docker-compose.prod.yml):**
- MongoDB: add `MONGO_INITDB_ROOT_USERNAME`/`MONGO_INITDB_ROOT_PASSWORD` env vars, update connection string to include auth
- Redis: add `--requirepass ${REDIS_PASSWORD}` to command, update connection string

### 1.4 Exposed Service Ports

**`docker-compose.yml:46,62,69-70`** — MongoDB (27017), Redis (6379), Neo4j (7474/7687) all exposed to host.
**Fix (docker-compose.prod.yml):** Remove `ports` mappings for all data stores. They should only be reachable through the Docker network. If admin access is needed, use `docker exec` or SSH tunnels.

### 1.5 Missing `.env.example`

**No `.env.example` exists** to document required environment variables.
**Fix:** Create `backend/.env.example` listing all required/optional vars with descriptions.

---

## 2. Error Handling Overhaul

### 2.1 No Global Exception Handler

**`backend/src/main.py`** — No `@app.exception_handler` registered. Unhandled exceptions return FastAPI's default 500 with `{"detail": "Internal Server Error"}`, which varies in shape from the `HTTPException` responses.

**Fix:** Add a global exception handler and a standard error response model:

**New file: `backend/src/api/errors.py`**
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    request_id: str | None = None

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        log.error("Unhandled exception [%s]: %s", request_id, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred" if settings.environment != "development" else str(exc),
                request_id=request_id,
            ).model_dump(),
        )
```

**`backend/src/main.py`** — Call `register_exception_handlers(app)` after app creation.

### 2.2 Raw Exception Leakage

**`backend/src/api/thinking.py:279`** — Leaks raw exception string to client:
```python
raise HTTPException(status_code=500, detail=str(e))
```
**Fix:** Log the full exception server-side, return a sanitized error to the client. In production, never expose `str(e)` in HTTP responses — it may contain stack traces, file paths, or sensitive data.

### 2.3 Inconsistent Error Response Shape

Currently, errors return `{"detail": "..."}` (FastAPI's HTTPException format). Some endpoints return ad-hoc shapes.

**Fix:** Adopt `ErrorResponse` model consistently. Override FastAPI's default `HTTPException` handler to return the standard shape:
```python
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=exc.detail, request_id=...).model_dump(),
    )
```

---

## 3. Logging & Observability

### 3.1 Plain Text Logging → JSON Structured

**`backend/src/core/logger.py`** — Uses plain text format `%(asctime)s %(levelname)-5s [%(name)s] %(message)s`. Not machine-parseable for log aggregation (ELK, CloudWatch, Datadog).

**Fix:** Add JSON logging mode toggled by `LOG_FORMAT` env var:
```python
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)
```

Use JSON formatter when `LOG_FORMAT=json` (default in production).

### 3.2 No Request/Response Middleware

**`backend/src/main.py`** — No middleware for:
- Request ID generation/propagation
- Request/response timing
- Request logging

**Fix:** Add `RequestMiddleware`:
```python
# backend/src/middleware/request_logging.py
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = request_id
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        log.info(
            "request",
            extra={"method": request.method, "path": request.url.path,
                   "status": response.status_code, "duration_ms": round(duration_ms, 1),
                   "request_id": request_id}
        )
        response.headers["X-Request-ID"] = request_id
        return response
```

### 3.3 No Health Check for Neo4j

**`backend/src/api/health.py:20-53`** — Readiness probe checks MongoDB and Redis but **not Neo4j**, which is a critical dependency for graph features.

**Fix:** Add Neo4j health check to readiness:
```python
# Neo4j check
try:
    from src.graph.dependencies import get_graph_store
    store = get_graph_store()
    await asyncio.wait_for(store.run_cypher("RETURN 1"), timeout=2.0)
    checks["neo4j"] = "ok"
except Exception:
    checks["neo4j"] = "error: not connected"
```

---

## 4. Deployment Hardening

### 4.1 Production Docker Compose Gaps

**`docker-compose.prod.yml`** — Currently only overrides volumes and commands. Missing:

**Fix — expand `docker-compose.prod.yml`:**
```yaml
services:
  backend:
    environment:
      ENVIRONMENT: production
      LOG_FORMAT: json
      NEO4J_PASSWORD: ${NEO4J_PASSWORD}
      SECRET_KEY: ${SECRET_KEY}
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "2.0"
      restart_policy:
        condition: on-failure
        max_attempts: 3

  frontend:
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: "0.5"

  mongodb:
    ports: []  # Remove host exposure
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_USER}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}
    deploy:
      resources:
        limits:
          memory: 1G

  redis:
    ports: []
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}", "--maxmemory", "256mb", "--maxmemory-policy", "allkeys-lru"]
    deploy:
      resources:
        limits:
          memory: 512M

  neo4j:
    ports: []  # Remove 7474/7687 host exposure
    deploy:
      resources:
        limits:
          memory: 2G
```

### 4.2 Nginx Hardening

**`frontend/nginx.conf`** — Missing security headers.

**Fix — add to `frontend/nginx.conf`:**
```nginx
# Additional security headers
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# Rate limiting zone (add to http block or top of server block)
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
location /api/ {
    limit_req zone=api burst=50 nodelay;
    # ... existing proxy config ...
}
```

### 4.3 CI Pipeline Gaps

**`.github/workflows/pr-checks.yml`** — Missing:
1. **No Neo4j service** — graph-related tests can't run in CI
2. **No Docker build test** — Dockerfile regressions caught only at deploy time
3. **No security scanning**

**Fix — add to `pr-checks.yml`:**
```yaml
  # Add Neo4j to backend-tests services
  services:
    neo4j:
      image: neo4j:5.26-community
      ports: ["7687:7687"]
      env:
        NEO4J_AUTH: neo4j/test-password
        NEO4J_PLUGINS: '["apoc"]'

  # New job: Docker build smoke test
  docker-build:
    name: Docker Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose build

  # New job: Security scan
  security:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
```

### 4.4 Missing `.env.example`

**New file: `backend/.env.example`**
```env
# Required in production
ENVIRONMENT=production
SECRET_KEY=           # Random 32+ char string
NEO4J_PASSWORD=       # Strong password, must match NEO4J_AUTH
SILICONFLOW_API_KEY=  # SiliconFlow/OpenAI-compatible API key

# Optional — data sources
PERIGON_API_KEY=
NEWSAPI_API_KEY=
ALPHA_VANTAGE_API_KEY=

# Defaults (override if needed)
MONGODB_URL=mongodb://mongodb:27017/financial_agent_v2
REDIS_URL=redis://redis:6379/0
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## 5. Resilience

### 5.1 No Retry on External API Calls

**`backend/src/services/perigon.py:246`**, **`newsapi.py:184`**, **`data_sources.py:51`** — All create a fresh `httpx.AsyncClient` per call with no retry:
```python
async with httpx.AsyncClient(timeout=15) as client:
    r = await client.get(...)
```

**Fix:** Create a shared resilient HTTP client with retry and connection pooling:

**New file: `backend/src/core/http.py`**
```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Module-level client with connection pooling
_client: httpx.AsyncClient | None = None

def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
)
async def resilient_get(url: str, **kwargs) -> httpx.Response:
    return await get_http_client().get(url, **kwargs)
```

Add `tenacity` to `pyproject.toml` dependencies.

### 5.2 Agent Retry Has No Backoff

**`backend/src/services/thinking_service.py:64-81`** — `_call_with_retry` retries immediately with no delay:
```python
for attempt in range(1 + AGENT_RETRIES):
    try: ...
    except Exception as e: ...  # No sleep between retries
```

**Fix:** Add exponential backoff:
```python
async def _call_with_retry(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    last_err = None
    for attempt in range(1 + AGENT_RETRIES):
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                timeout=AGENT_TIMEOUT_S,
            )
        except Exception as e:
            last_err = e
            if attempt < AGENT_RETRIES:
                delay = min(2 ** attempt, 10)
                log.warning("Agent call failed (attempt %d), retrying in %ds: %s", attempt + 1, delay, e)
                await asyncio.sleep(delay)
    raise last_err
```

### 5.3 MongoDB Client Missing Pool Configuration

**`backend/src/database/mongodb.py:10`**:
```python
self.client = AsyncIOMotorClient(url)
```

**Fix:** Add connection pool and timeout options:
```python
self.client = AsyncIOMotorClient(
    url,
    maxPoolSize=20,
    minPoolSize=2,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=30000,
)
```

### 5.4 Redis No Reconnect

**`backend/src/database/redis.py:14-20`** — If initial ping fails, `self.client = None` permanently. No reconnect logic.

**Fix:** Add a reconnect wrapper:
```python
async def connect(self, url: str) -> None:
    self._url = url
    self.client = aioredis.from_url(url, decode_responses=True, retry_on_timeout=True)
    await self.client.ping()

async def ensure_connected(self) -> aioredis.Redis:
    if self.client is None and hasattr(self, '_url'):
        await self.connect(self._url)
    return self._connected()
```

### 5.5 No Graceful Shutdown for SSE Sessions

**`backend/src/services/session_events.py`** — When the app shuts down, active SSE sessions are not notified. Clients hang until their connection times out.

**Fix:** Add a `shutdown_all()` method to `SessionRegistry` and call it from lifespan:
```python
async def shutdown_all(self):
    for sid in list(self._sessions):
        entry = self._sessions[sid]
        await entry.queue.put(SSEEvent(event="error", data={"error": "Server shutting down"}, id="shutdown"))
        self.remove(sid)
```

---

## 6. API Contract

### 6.1 Missing Response Models

Several endpoints return raw dicts or MongoDB documents without Pydantic response models:

| Endpoint | File:Line | Issue |
|----------|-----------|-------|
| `GET /api/thinking/{id}` | `thinking.py:147` | Returns raw MongoDB doc, no response model |
| `POST /api/thinking/{id}/match` | `thinking.py:365` | Returns `{"opportunities": [...]}`, no model |
| `GET /api/health/ready` | `health.py:21` | Returns ad-hoc dict, no model |

**Fix:** Add Pydantic response models for all endpoints. At minimum:
```python
class SessionResponse(BaseModel):
    id: str
    status: str
    current_layer: int
    nodes: list[dict]
    edges: list[dict]
    # ... all fields

class MatchResponse(BaseModel):
    opportunities: list[dict]

class HealthResponse(BaseModel):
    status: str
    mongodb: str | None = None
    redis: str | None = None
    neo4j: str | None = None
```

### 6.2 No API Versioning

**`backend/src/main.py:128-133`** — All routers use `/api/` prefix with no version.

**Fix:** Add version prefix. Either:
- Rename all router prefixes to `/api/v1/...`
- Or add a versioned sub-application: `app.mount("/api/v1", v1_app)`

This is a breaking change — coordinate with frontend.

### 6.3 OpenAPI Metadata

**`backend/src/main.py:120`**:
```python
app = FastAPI(title="Nexis", lifespan=lifespan)
```

**Fix:** Add production metadata:
```python
app = FastAPI(
    title="Nexis Financial Agent",
    description="AI-powered financial analysis pipeline",
    version="0.2.0",
    docs_url="/api/docs" if settings.environment == "development" else None,
    redoc_url=None,
)
```
Disable Swagger UI in production — it exposes the full API schema.

### 6.4 No Rate Limiting

No rate limiting on any endpoint. A single client can exhaust LLM API quotas via rapid `/thinking/auto` calls.

**Fix:** Add rate limiting middleware. Options:
- `slowapi` (lightweight, Redis-backed): limit `/api/thinking/auto` to 5 req/min per IP
- nginx-level rate limiting (already shown in 4.2)

---

## Priority Matrix

| Priority | Section | Effort | Risk if Skipped |
|----------|---------|--------|-----------------|
| P0 | 1.1 Hardcoded secrets | Low | Credential leak |
| P0 | 1.3 DB auth | Medium | Data breach |
| P0 | 2.2 Exception leakage | Low | Info disclosure |
| P1 | 3.1 JSON logging | Medium | Ops blind spot |
| P1 | 3.2 Request middleware | Medium | No request tracing |
| P1 | 4.1 Prod compose | Medium | Resource exhaustion |
| P1 | 5.1 HTTP retry/pooling | Medium | Cascading failures |
| P1 | 5.3 MongoDB pool config | Low | Connection exhaustion |
| P2 | 1.2 CORS tightening | Low | CSRF risk |
| P2 | 2.1 Global error handler | Medium | Inconsistent errors |
| P2 | 4.2 Nginx headers | Low | XSS/clickjacking |
| P2 | 4.3 CI additions | Medium | Regression risk |
| P2 | 6.1 Response models | High | Unstable API contract |
| P3 | 5.5 SSE graceful shutdown | Low | Client hangs |
| P3 | 6.2 API versioning | High | Breaking change |
| P3 | 6.3 OpenAPI metadata | Low | Schema exposure |

---

## Files Changed Summary

| File | Changes |
|------|---------|
| `backend/src/core/config.py` | Remove secret defaults, add startup validator |
| `backend/src/graph/config.py` | Remove password default |
| `backend/src/services/data_sources.py` | Remove hardcoded Alpha Vantage key |
| `backend/src/services/perigon.py` | Use `settings.perigon_api_key` instead of `os.environ` |
| `backend/src/main.py` | Tighten CORS, register error handlers, add middleware, update OpenAPI |
| `backend/src/core/logger.py` | Add JSON formatter, `LOG_FORMAT` toggle |
| `backend/src/core/http.py` | **NEW** — shared resilient HTTP client |
| `backend/src/api/errors.py` | **NEW** — error response model + handlers |
| `backend/src/middleware/request_logging.py` | **NEW** — request ID + timing middleware |
| `backend/src/api/health.py` | Add Neo4j health check |
| `backend/src/api/thinking.py` | Add response models, sanitize error output |
| `backend/src/database/mongodb.py` | Add pool/timeout options |
| `backend/src/database/redis.py` | Add reconnect logic |
| `backend/src/services/thinking_service.py` | Add backoff to retry |
| `backend/src/services/session_events.py` | Add `shutdown_all()` |
| `docker-compose.yml` | Use env var substitution for secrets |
| `docker-compose.prod.yml` | Resource limits, DB auth, port removal |
| `frontend/nginx.conf` | Security headers, rate limiting |
| `.github/workflows/pr-checks.yml` | Neo4j service, Docker build, security scan |
| `backend/.env.example` | **NEW** — document required env vars |
| `backend/pyproject.toml` | Add `tenacity` dependency |
