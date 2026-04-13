import asyncio

from fastapi import APIRouter, Response

from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.database.redis import redis_client

log = get_logger("api.health")

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live")
async def liveness():
    """Liveness probe — process is alive, no dependency checks."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(response: Response):
    """Readiness probe — checks MongoDB and Redis connectivity."""
    checks: dict[str, str] = {}

    # MongoDB check with 2s timeout
    try:
        await asyncio.wait_for(mongodb.db.command("ping"), timeout=2.0)
        checks["mongodb"] = "ok"
    except asyncio.TimeoutError:
        log.warning("MongoDB health check timed out", exc_info=True)
        checks["mongodb"] = "error: timeout"
    except Exception:
        log.warning("MongoDB health check failed", exc_info=True)
        checks["mongodb"] = "error: not connected"

    # Redis check with 2s timeout
    try:
        if redis_client.client is None:
            raise RuntimeError("not connected")
        await asyncio.wait_for(redis_client.client.ping(), timeout=2.0)
        checks["redis"] = "ok"
    except asyncio.TimeoutError:
        log.warning("Redis health check timed out", exc_info=True)
        checks["redis"] = "error: timeout"
    except Exception:
        log.warning("Redis health check failed", exc_info=True)
        checks["redis"] = "error: not connected"

    # Neo4j check with 2s timeout
    try:
        from src.graph.dependencies import get_graph_store

        store = get_graph_store()
        # Verify the store is initialized and responsive
        await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, lambda: store is not None),
            timeout=2.0,
        )
        checks["neo4j"] = "ok"
    except RuntimeError:
        # Graph services not initialized — optional dependency
        checks["neo4j"] = "not initialized"
    except asyncio.TimeoutError:
        log.warning("Neo4j health check timed out", exc_info=True)
        checks["neo4j"] = "error: timeout"
    except Exception as e:
        log.warning("Neo4j health check failed: %s", e, exc_info=True)
        checks["neo4j"] = f"error: {e}"

    # Neo4j "not initialized" is acceptable — it's an optional service
    _acceptable = {"ok", "not initialized"}
    healthy = all(v in _acceptable for v in checks.values())
    if not healthy:
        response.status_code = 503

    return {"status": "ok" if healthy else "degraded", **checks}


@router.get("/startup")
async def startup():
    """Startup probe — same as liveness (process booted)."""
    return {"status": "ok"}


@router.get("")
async def health_legacy():
    """Backward-compatible health endpoint."""
    return {"status": "ok", "version": "0.1.0"}
