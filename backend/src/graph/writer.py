"""Async graph writer — fire-and-forget writes to Neo4j during normal operations."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from src.graph.protocols import GraphStore

logger = logging.getLogger(__name__)


class GraphWriter:
    """Handles async graph writes. All writes are non-blocking and non-fatal."""

    def __init__(self, store: GraphStore, group_id: str = "nexis") -> None:
        self._store = store
        self._group_id = group_id

    async def ingest_news_article(
        self,
        title: str,
        summary: str,
        source: str = "news",
        published_at: datetime | None = None,
    ) -> None:
        """Ingest a news article as a Graphiti episode (async, non-fatal)."""
        from src.graph.entities import NEWS_ENTITY_TYPES
        from src.graph.edges import NEWS_EDGE_TYPES

        try:
            body = f"{title}\n\n{summary}" if summary else title
            await self._store.add_episode(
                name=title[:100],
                body=body,
                source_description=f"news_{source}",
                group_id=self._group_id,
                reference_time=published_at or datetime.now(timezone.utc),
                entity_types=NEWS_ENTITY_TYPES,
                edge_types=NEWS_EDGE_TYPES,
            )
            logger.debug("Graph: ingested news '%s'", title[:60])
        except Exception:
            logger.warning(
                "Graph: failed to ingest news '%s'", title[:60], exc_info=True
            )

    async def ingest_news_batch(self, articles: list[dict[str, Any]]) -> None:
        """Ingest a batch of news articles. Each is independent — failures don't block others."""
        for article in articles:
            await self.ingest_news_article(
                title=article.get("title", article.get("canonical_title", "")),
                summary=article.get("summary", article.get("description", "")),
                source=article.get("source", "unknown"),
                published_at=article.get("published_at"),
            )

    async def ingest_thinking_node(
        self,
        content: str,
        reasoning: str = "",
        node_type: str = "effect",
        layer: int = 0,
        session_id: str = "",
    ) -> None:
        """Ingest a thinking pipeline output (effect/opportunity) as an episode."""
        from src.graph.entities import THINKING_ENTITY_TYPES
        from src.graph.edges import THINKING_EDGE_TYPES

        try:
            body = f"{content}\n\nReasoning: {reasoning}" if reasoning else content
            source_desc = f"thinking_{node_type}_layer{layer}"
            if session_id:
                source_desc += f"_session_{session_id[:8]}"

            await self._store.add_episode(
                name=content[:100],
                body=body,
                source_description=source_desc,
                group_id=self._group_id,
                reference_time=datetime.now(timezone.utc),
                entity_types=THINKING_ENTITY_TYPES,
                edge_types=THINKING_EDGE_TYPES,
            )
            logger.debug("Graph: ingested %s node '%s'", node_type, content[:60])
        except Exception:
            logger.warning(
                "Graph: failed to ingest %s node '%s'",
                node_type,
                content[:60],
                exc_info=True,
            )

    async def ingest_thinking_layer(
        self,
        session_id: str,
        layer: int,
        nodes: list[dict[str, Any]],
    ) -> None:
        """Ingest all nodes from a thinking layer. Each node is independent."""
        for node in nodes:
            await self.ingest_thinking_node(
                content=node.get("content", ""),
                reasoning=node.get("reasoning", ""),
                node_type=node.get("type", "effect"),
                layer=layer,
                session_id=session_id,
            )


def try_ingest_thinking_layer(
    session_id: str, layer: int, nodes: list[dict[str, Any]]
) -> None:
    """Best-effort graph write for a thinking layer. No-op if graph not initialized."""
    try:
        from src.graph.dependencies import get_graph_store

        store = get_graph_store()
        writer = GraphWriter(store)
        fire_and_forget(writer.ingest_thinking_layer(session_id, layer, nodes))
    except RuntimeError:
        pass  # Graph services not initialized


def try_ingest_news_batch(articles: list[dict[str, Any]]) -> None:
    """Best-effort graph write for a news batch. No-op if graph not initialized."""
    try:
        from src.graph.dependencies import get_graph_store

        store = get_graph_store()
        writer = GraphWriter(store)
        fire_and_forget(writer.ingest_news_batch(articles))
    except RuntimeError:
        pass  # Graph services not initialized


def fire_and_forget(coro: Any) -> None:
    """Schedule a coroutine as a background task. Logs but does not propagate errors."""

    async def _wrapper() -> None:
        try:
            await coro
        except Exception:
            logger.warning("Graph background write failed", exc_info=True)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_wrapper())
    except RuntimeError:
        logger.warning("No running event loop — skipping graph background write")
