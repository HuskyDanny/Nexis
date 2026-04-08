"""Composition root — wires concrete implementations together.

DEPRECATED: RAG services (Qdrant-based) are replaced by graph services
(src/graph/dependencies.py). This module is kept for backwards compatibility.
See src/graph/dependencies.py for the active implementation.
"""

from __future__ import annotations

from src.core.logger import get_logger

log = get_logger("rag")


async def init_rag_services() -> None:
    """Deprecated — graph services handle knowledge storage now.

    Kept as a no-op so existing callers (main.py lifespan) don't break.
    Use src.graph.dependencies.init_graph_services() instead.
    """
    log.info("RAG services deprecated — graph services handle knowledge storage")


async def close_rag_services() -> None:
    """Deprecated — no resources to clean up."""
    pass
