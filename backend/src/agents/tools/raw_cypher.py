"""Tier 2 graph tool — raw Cypher escape hatch (last resort)."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.core.logger import get_logger
from src.graph.protocols import GraphStore

log = get_logger("raw_cypher_tool")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class RawCypherInput(BaseModel):
    """Input schema for raw_cypher tool."""

    query: str = Field(..., description="Read-only Cypher query")
    params: dict = Field(default_factory=dict, description="Query parameters")


class RawCypherTool(BaseTool):
    name: str = "raw_cypher"
    description: str = (
        "Execute a raw read-only Cypher query against the knowledge graph. "
        "LAST RESORT — use graph_search, explore_entity, or find_paths first. "
        "Only for complex aggregations or structural queries the other tools can't express. "
        "Write operations (CREATE, MERGE, DELETE) are blocked."
    )
    args_schema: Type[BaseModel] = RawCypherInput

    graph_store: GraphStore = Field(exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, query: str, params: dict | None = None) -> list[dict]:
        """Sync wrapper for CrewAI compatibility."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.arun(query=query, params=params or {})
        if loop and loop.is_running():
            future = _executor.submit(asyncio.run, coro)
            return future.result()
        return asyncio.run(coro)

    async def arun(self, query: str, params: dict | None = None) -> list[dict]:
        """Execute read-only Cypher."""
        rows = await self.graph_store.run_cypher(query, params=params or {})
        log.info("raw_cypher: %d rows returned", len(rows))
        return rows
