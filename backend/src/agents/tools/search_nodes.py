"""Agent tool for searching the node knowledge base via RAG."""

import asyncio

from crewai.tools import BaseTool
from pydantic import Field

from src.core.logger import get_logger
from src.rag.search import NodeSearchService

log = get_logger("search_nodes_tool")


class SearchNodesTool(BaseTool):
    name: str = "search_nodes"
    description: str = (
        "Search the knowledge base of previously analyzed nodes — effects, "
        "opportunities, news, and fetch results from prior sessions. "
        "This is fast, free (no API cost), and reuses existing analysis. "
        "Prefer this tool BEFORE fetching live news. Use filters to narrow "
        "results to what's relevant for your current reasoning.\n\n"
        "Parameters:\n"
        "- query (required): semantic search text\n"
        "- node_type: 'effect', 'opportunity', 'news', or 'fetch'\n"
        "- sector: e.g. 'technology', 'energy', 'healthcare'\n"
        "- min_confidence: minimum confidence score (0-100)\n"
        "- date_from: earliest date (YYYY-MM-DD)\n"
        "- date_to: latest date (YYYY-MM-DD)\n"
        "- market: 'US' or 'CN'\n"
        "- limit: max results (default 20)"
    )

    search_service: NodeSearchService = Field(exclude=True)
    session_id: str = Field(exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def _run(
        self,
        query: str,
        node_type: str | None = None,
        sector: str | None = None,
        min_confidence: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        market: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Sync wrapper for CrewAI compatibility.

        Uses the existing event loop when available (via run_coroutine_threadsafe)
        to avoid creating a second loop that conflicts with singleton async clients.
        Falls back to asyncio.run() only when no loop is running.
        """
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
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        # Schedule on the existing loop from a worker thread
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    async def arun(
        self,
        query: str,
        node_type: str | None = None,
        sector: str | None = None,
        min_confidence: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        market: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Async search implementation."""
        type_list = [node_type] if isinstance(node_type, str) else node_type

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
