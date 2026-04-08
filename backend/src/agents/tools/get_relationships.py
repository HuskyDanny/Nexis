"""Tier 2 graph tool — list relationship types for an entity."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.core.logger import get_logger
from src.graph.protocols import GraphStore

log = get_logger("get_relationships_tool")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class GetRelationshipsInput(BaseModel):
    """Input schema for get_relationships tool."""

    entity_name: str = Field(..., description="Entity name to inspect")


class GetRelationshipsTool(BaseTool):
    name: str = "get_relationships"
    description: str = (
        "List all relationship types and counts for an entity. "
        "Use BEFORE explore_entity to see what types exist, then decide "
        "which to drill into. 'Look at the map before walking.'"
    )
    args_schema: Type[BaseModel] = GetRelationshipsInput

    graph_store: GraphStore = Field(exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, entity_name: str) -> list[dict]:
        """Sync wrapper for CrewAI compatibility."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.arun(entity_name=entity_name)
        if loop and loop.is_running():
            future = _executor.submit(asyncio.run, coro)
            return future.result()
        return asyncio.run(coro)

    async def arun(self, entity_name: str) -> list[dict]:
        """Get relationship type summary."""
        rels = await self.graph_store.get_relationships(entity_name)
        log.info("get_relationships: '%s' -> %d types", entity_name, len(rels))
        return rels
