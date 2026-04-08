"""Tier 1 graph tool — semantic search with graph context.

Handles 80% of queries in a single call. Returns facts + entity metadata.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.core.logger import get_logger
from src.graph.protocols import GraphStore

log = get_logger("graph_search_tool")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class GraphSearchInput(BaseModel):
    """Input schema for graph_search tool."""

    query: str = Field(
        ..., description="Semantic search text — describe what you're looking for"
    )
    limit: int = Field(
        default=20, ge=1, le=100, description="Maximum results to return"
    )


class GraphSearchTool(BaseTool):
    name: str = "graph_search"
    description: str = (
        "Search the knowledge graph for entities and their relationships. "
        "Returns facts with graph context — connected events, causal chains, "
        "and related companies. Prefer this BEFORE fetching live news. "
        "For 80% of questions, one call to this tool is enough."
    )
    args_schema: Type[BaseModel] = GraphSearchInput

    graph_store: GraphStore = Field(exclude=True)
    group_id: str = Field(default="nexis", exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, query: str, limit: int = 20) -> list[dict]:
        """Sync wrapper for CrewAI compatibility."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.arun(query=query, limit=limit)
        if loop and loop.is_running():
            future = _executor.submit(asyncio.run, coro)
            return future.result()
        return asyncio.run(coro)

    async def arun(self, query: str, limit: int = 20) -> list[dict]:
        """Async search — hybrid BM25 + cosine + graph structure."""
        results = await self.graph_store.search(
            query=query,
            group_ids=[self.group_id],
            limit=limit,
        )
        log.info("graph_search: query='%s' results=%d", query, len(results))
        return results
