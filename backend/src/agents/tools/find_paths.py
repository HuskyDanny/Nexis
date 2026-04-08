"""Tier 2 graph tool — discover how two entities are connected."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.core.logger import get_logger
from src.graph.protocols import GraphStore

log = get_logger("find_paths_tool")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class FindPathsInput(BaseModel):
    """Input schema for find_paths tool."""

    source: str = Field(..., description="Source entity name")
    target: str = Field(..., description="Target entity name")
    max_hops: int = Field(default=4, ge=1, le=6, description="Maximum path length")


class FindPathsTool(BaseTool):
    name: str = "find_paths"
    description: str = (
        "Discover how two entities are connected through causal chains. "
        "Use when the question asks HOW things are related. "
        "Returns paths with intermediate entities and edge facts."
    )
    args_schema: Type[BaseModel] = FindPathsInput

    graph_store: GraphStore = Field(exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, source: str, target: str, max_hops: int = 4) -> list[dict]:
        """Sync wrapper for CrewAI compatibility."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.arun(source=source, target=target, max_hops=max_hops)
        if loop and loop.is_running():
            future = _executor.submit(asyncio.run, coro)
            return future.result()
        return asyncio.run(coro)

    async def arun(self, source: str, target: str, max_hops: int = 4) -> list[dict]:
        """Find paths between two entities."""
        paths = await self.graph_store.find_paths(source, target, max_hops=max_hops)
        log.info("find_paths: '%s' -> '%s' = %d paths", source, target, len(paths))
        return paths
