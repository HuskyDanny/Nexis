from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):  # noqa: ARG001
    from src.database.mongodb import mongodb

    await mongodb.connect(settings.mongodb_url)
    yield
    await mongodb.close()


app = FastAPI(title="Financial Agent v2", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


from src.api.graphs import router as graphs_router
from src.api.nodes import router as nodes_router

app.include_router(graphs_router)
app.include_router(nodes_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
