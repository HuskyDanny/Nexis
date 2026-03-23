from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):  # noqa: ARG001
    from src.database.mongodb import mongodb

    log.info("Starting up — connecting to MongoDB")
    await mongodb.connect(settings.mongodb_url)
    log.info("MongoDB connected")
    yield
    log.info("Shutting down")
    await mongodb.close()


app = FastAPI(title="Nexis", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


from src.api.graphs import router as graphs_router
from src.api.nodes import router as nodes_router
from src.api.pools import router as pools_router
from src.api.thinking import router as thinking_router

app.include_router(graphs_router)
app.include_router(nodes_router)
app.include_router(pools_router)
app.include_router(thinking_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
