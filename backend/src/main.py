import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.errors import register_exception_handlers
from src.api.graphs import router as graphs_router
from src.api.health import router as health_router
from src.api.nodes import router as nodes_router
from src.api.pools import router as pools_router
from src.api.thinking import router as thinking_router
from src.api.thinking_auto import router as thinking_auto_router
from src.core.config import settings
from src.core.logger import get_logger
from src.cron.manager import CronManager, JobConfig
from src.database.mongodb import mongodb
from src.database.redis import redis_client
from src.middleware.request_logging import RequestMiddleware
from src.services.session_events import registry

log = get_logger("app")

cron = CronManager()


async def _periodic_health_check():
    """Run SSE session health check every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        await registry.health_check()


@asynccontextmanager
async def lifespan(_: FastAPI):  # noqa: ARG001
    log.info("Starting up — connecting to MongoDB")
    await mongodb.connect(settings.mongodb_url)
    log.info("MongoDB connected")

    # Sweep stuck sessions (thinking for >10 min) → mark as timeout
    from datetime import datetime, timezone, timedelta

    col = mongodb.get_collection("thinking_sessions")
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    result = await col.update_many(
        {"status": "thinking", "created_at": {"$lt": cutoff}},
        {"$set": {"status": "timeout"}},
    )
    if result.modified_count:
        log.info("Cleaned up %d stuck thinking sessions", result.modified_count)

    log.info("Connecting to Redis")
    try:
        await redis_client.connect(settings.redis_url)
        log.info("Redis connected")
    except Exception as e:
        log.warning("Redis connection failed (non-fatal): %s", e)

    # Initialize graph services (Neo4j + Graphiti)
    from src.graph.dependencies import init_graph_services, close_graph_services

    try:
        await init_graph_services()
        log.info("Graph services initialized")
    except Exception as e:
        log.warning("Graph initialization failed (non-fatal): %s", e)

    # Register cron jobs (lazy import to avoid circular deps)
    from src.cron.scheduler import run_news_pipeline, run_value_pipeline

    cron.register(
        JobConfig(
            name="news_pipeline",
            handler=run_news_pipeline,
            interval_seconds=settings.news_cron_interval_hours * 3600,
            max_retries=2,
            run_on_start=True,
        )
    )
    cron.register(
        JobConfig(
            name="value_pipeline",
            handler=run_value_pipeline,
            interval_seconds=settings.news_cron_interval_hours * 3600,
            max_retries=2,
            run_on_start=True,
        )
    )
    await cron.start_all()

    # SSE health check (not a cron job — lightweight, high-frequency)
    health_task = asyncio.create_task(_periodic_health_check())

    yield

    log.info("Shutting down")

    # Drain active SSE sessions first (notify clients)
    await registry.shutdown_all()

    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass

    await cron.shutdown()

    # Close shared HTTP client pool
    try:
        from src.core.http import close_http_client

        await close_http_client()
    except (ImportError, Exception) as e:
        log.debug("HTTP client close skipped: %s", e)

    try:
        await close_graph_services()
    except Exception as e:
        log.debug("Graph services close failed (non-fatal): %s", e)
    await redis_client.close()
    await mongodb.close()


app = FastAPI(
    title="Nexis",
    version="0.2.0",
    docs_url=None if settings.environment == "production" else "/docs",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(RequestMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

app.include_router(health_router)
app.include_router(graphs_router)
app.include_router(nodes_router)
app.include_router(pools_router)
app.include_router(thinking_router)
app.include_router(thinking_auto_router)
