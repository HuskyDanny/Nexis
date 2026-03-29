"""Agent tool for searching the node knowledge base via RAG."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.core.logger import get_logger
from src.rag.search import NodeSearchService

log = get_logger("search_nodes_tool")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class SearchNodesInput(BaseModel):
    """Input schema for the search_nodes tool. Pydantic Field descriptions
    are auto-injected into the tool schema sent to the LLM."""

    query: str = Field(
        ..., description="Semantic search text — describe what you're looking for"
    )
    node_type: list[str] | None = Field(
        default=None,
        description="Filter by node type: 'effect', 'opportunity', 'news', or 'fetch'",
    )
    sector: str | None = Field(
        default=None,
        description="Filter by sector, e.g. 'technology', 'energy', 'healthcare'",
    )
    min_confidence: float | None = Field(
        default=None, ge=0, le=100, description="Minimum confidence score (0-100)"
    )
    date_from: str | None = Field(
        default=None, description="Earliest date filter (YYYY-MM-DD)"
    )
    date_to: str | None = Field(
        default=None, description="Latest date filter (YYYY-MM-DD)"
    )
    market: str | None = Field(
        default=None, description="Filter by market: 'US' or 'CN'"
    )
    limit: int = Field(
        default=20, ge=1, le=100, description="Maximum number of results to return"
    )


class SearchNodesTool(BaseTool):
    name: str = "search_nodes"
    description: str = (
        "Search the knowledge base of previously analyzed nodes — effects, "
        "opportunities, news, and fetch results from prior sessions. "
        "This is fast, free (no API cost), and reuses existing analysis. "
        "Prefer this tool BEFORE fetching live news. Use filters to narrow "
        "results to what's relevant for your current reasoning."
    )
    args_schema: Type[BaseModel] = SearchNodesInput

    search_service: NodeSearchService = Field(exclude=True)
    session_id: str = Field(exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def _run(
        self,
        query: str,
        node_type: list[str] | None = None,
        sector: str | None = None,
        min_confidence: float | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        market: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Sync wrapper for CrewAI compatibility.

        When a loop is already running (CrewAI context), offloads to a separate
        thread via a module-level executor to avoid deadlocks. Falls back to
        asyncio.run() when no loop is running.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.arun(
            query=query,
            node_type=node_type,
            sector=sector,
            min_confidence=min_confidence,
            date_from=date_from,
            date_to=date_to,
            market=market,
            limit=limit,
        )

        if loop and loop.is_running():
            future = _executor.submit(asyncio.run, coro)
            return future.result()
        else:
            return asyncio.run(coro)

    async def arun(
        self,
        query: str,
        node_type: list[str] | None = None,
        sector: str | None = None,
        min_confidence: float | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        market: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Async search implementation."""
        type_list = node_type or []

        results = await self.search_service.search(
            query=query,
            current_session_id=self.session_id,
            node_type=type_list,
            sector=sector,
            min_confidence=min_confidence,
            date_from=date_from,
            date_to=date_to,
            market=market,
            limit=limit,
        )
        log.info("search_nodes: %d results for '%s'", len(results), query)
        return results
