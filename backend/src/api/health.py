import asyncio
import os

from fastapi import APIRouter, Response

from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.database.redis import redis_client

log = get_logger("api.health")

HEALTH_CHECK_TIMEOUT = float(os.environ.get("HEALTH_CHECK_TIMEOUT", "2.0"))

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live")
async def liveness():
    """Liveness probe — process is alive, no dependency checks."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(response: Response):
    """Readiness probe — checks MongoDB and Redis connectivity."""
    checks: dict[str, str] = {}

    # MongoDB check
    try:
        await asyncio.wait_for(mongodb.db.command("ping"), timeout=HEALTH_CHECK_TIMEOUT)
        checks["mongodb"] = "ok"
    except asyncio.TimeoutError:
        log.warning("MongoDB health check timed out", exc_info=True)
        checks["mongodb"] = "error: timeout"
    except Exception:
        log.warning("MongoDB health check failed", exc_info=True)
        checks["mongodb"] = "error: not connected"

    # Redis check
    try:
        if redis_client.client is None:
            raise RuntimeError("not connected")
        await asyncio.wait_for(redis_client.client.ping(), timeout=HEALTH_CHECK_TIMEOUT)
        checks["redis"] = "ok"
    except asyncio.TimeoutError:
        log.warning("Redis health check timed out", exc_info=True)
        checks["redis"] = "error: timeout"
    except Exception:
        log.warning("Redis health check failed", exc_info=True)
        checks["redis"] = "error: not connected"

    all_ok = all(v == "ok" for v in checks.values())
    if not all_ok:
        response.status_code = 503

    return {"status": "ok" if all_ok else "degraded", **checks}


@router.get("/startup")
async def startup():
    """Startup probe — same as liveness (process booted)."""
    return {"status": "ok"}


@router.get("")
async def health_legacy():
    """Backward-compatible health endpoint."""
    return {"status": "ok", "version": "0.1.0"}
