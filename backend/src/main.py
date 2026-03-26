from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.graphs import router as graphs_router
from src.api.health import router as health_router
from src.api.nodes import router as nodes_router
from src.api.pools import router as pools_router
from src.api.thinking import router as thinking_router
from src.api.thinking_auto import router as thinking_auto_router
from src.core.config import settings
from src.core.logger import get_logger
from src.database.mongodb import mongodb
from src.database.redis import redis_client

log = get_logger("app")


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

    # Connect Qdrant + initialize RAG services
    from src.rag.dependencies import init_rag_services, close_rag_services

    try:
        await init_rag_services()
        log.info("RAG services initialized")
    except Exception as e:
        log.warning("RAG initialization failed (non-fatal): %s", e)

    yield
    log.info("Shutting down")
    from src.rag.dependencies import close_rag_services

    await close_rag_services()
    await redis_client.close()
    await mongodb.close()


app = FastAPI(title="Nexis", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(graphs_router)
app.include_router(nodes_router)
app.include_router(pools_router)
app.include_router(thinking_router)
app.include_router(thinking_auto_router)
