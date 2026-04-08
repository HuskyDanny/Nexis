"""Tier 2 graph tool — full neighborhood scan of an entity."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.core.logger import get_logger
from src.graph.protocols import GraphStore

log = get_logger("explore_entity_tool")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class ExploreEntityInput(BaseModel):
    """Input schema for explore_entity tool."""

    entity_name: str = Field(
        ..., description="Entity name to explore (e.g., 'NVIDIA', 'Federal Reserve')"
    )
    edge_types: list[str] | None = Field(
        default=None,
        description="Filter by edge type: 'IMPACTS', 'CAUSED_BY', 'MATCHES', 'IN_SECTOR', 'MENTIONS'",
    )
    limit: int = Field(
        default=50, ge=1, le=200, description="Maximum neighbors to return"
    )


class ExploreEntityTool(BaseTool):
    name: str = "explore_entity"
    description: str = (
        "Full neighborhood scan — 'tell me everything about X.' "
        "Returns the entity's summary and all connected nodes with relationship details. "
        "Use after graph_search reveals a high-degree entity you want to drill into."
    )
    args_schema: Type[BaseModel] = ExploreEntityInput

    graph_store: GraphStore = Field(exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def _run(
        self,
        entity_name: str,
        edge_types: list[str] | None = None,
        limit: int = 50,
    ) -> dict:
        """Sync wrapper for CrewAI compatibility."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.arun(entity_name=entity_name, edge_types=edge_types, limit=limit)
        if loop and loop.is_running():
            future = _executor.submit(asyncio.run, coro)
            return future.result()
        return asyncio.run(coro)

    async def arun(
        self,
        entity_name: str,
        edge_types: list[str] | None = None,
        limit: int = 50,
    ) -> dict:
        """Get entity + all neighbors."""
        entity = await self.graph_store.get_entity(entity_name)
        if not entity:
            return {
                "entity": None,
                "neighbors": [],
                "message": f"Entity '{entity_name}' not found",
            }

        neighbors = await self.graph_store.get_neighbors(
            entity_name, edge_types=edge_types, limit=limit
        )
        log.info("explore_entity: '%s' -> %d neighbors", entity_name, len(neighbors))
        return {"entity": entity, "neighbors": neighbors}
