"""Node search with hybrid retrieval and query-time decay re-ranking.

DEPRECATED: Search is now handled by graph tools (GraphSearchTool, etc.)
backed by Graphiti's built-in hybrid search. This module is kept for
backwards compatibility with existing tests.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.core.logger import get_logger
from src.rag.config import RAGConfig
from src.rag.decay import decay_score
from src.rag.protocols import EmbeddingProvider, SparseEncoder, VectorStore

log = get_logger("rag.search")


class NodeSearchService:
    def __init__(
        self,
        vector_store: VectorStore,
        embedder: EmbeddingProvider,
        sparse_encoder: SparseEncoder,
        config: RAGConfig,
    ):
        self.vector_store = vector_store
        self.embedder = embedder
        self.sparse_encoder = sparse_encoder
        self.config = config

    async def search(
        self,
        query: str,
        current_session_id: str,
        *,
        node_type: list[str] | None = None,
        sector: str | None = None,
        min_confidence: float | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        market: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """Search nodes with hybrid retrieval + decay re-ranking."""
        limit = limit or self.config.default_limit
        prefetch = self.config.prefetch_limit

        dense = await self.embedder.embed(query)
        sparse = self.sparse_encoder.encode(query)

        filters: dict = {"exclude_session_id": current_session_id}
        if node_type:
            filters["node_type"] = node_type
        if sector:
            filters["sector"] = sector
        if min_confidence is not None:
            filters["min_confidence"] = min_confidence
        if date_from:
            filters["date_from"] = date_from
        if date_to:
            filters["date_to"] = date_to
        if market:
            filters["market"] = market

        raw_results = await self.vector_store.query(
            self.config.collection_name,
            dense=dense,
            sparse=sparse,
            filters=filters,
            limit=prefetch,
        )

        now = datetime.now(timezone.utc)
        for r in raw_results:
            node_date = self._parse_date(r.get("date", ""))
            r["score"] = decay_score(
                r.get("score", 0.0),
                node_date,
                now,
                r.get("node_type", "effect"),
                self.config,
            )

        raw_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return raw_results[:limit]

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
        return datetime(2020, 1, 1, tzinfo=timezone.utc)
