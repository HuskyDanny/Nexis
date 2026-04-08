"""Composition root for graph services. Lazy imports to avoid heavy deps at module level."""

from __future__ import annotations

from src.graph.protocols import GraphStore

_graph_store: GraphStore | None = None


async def init_graph_services() -> GraphStore:
    """Initialize Graphiti client + Neo4j connection.

    Called during FastAPI lifespan startup.
    """
    from src.core.config import settings
    from src.graph.client import GraphitiStore
    from src.graph.config import GraphConfig

    config = GraphConfig(
        neo4j_uri=settings.neo4j_uri,
        neo4j_user=settings.neo4j_user,
        neo4j_password=settings.neo4j_password,
        llm_api_key=settings.siliconflow_api_key,
    )
    store = GraphitiStore(config)
    await store.initialize()

    global _graph_store
    _graph_store = store
    return store


def get_graph_store() -> GraphStore:
    """Get the initialized graph store. Raises if not yet initialized."""
    if _graph_store is None:
        raise RuntimeError(
            "Graph services not initialized — call init_graph_services() first"
        )
    return _graph_store


async def close_graph_services() -> None:
    """Close graph connections. Called during FastAPI lifespan shutdown."""
    global _graph_store
    if _graph_store:
        await _graph_store.close()
        _graph_store = None
