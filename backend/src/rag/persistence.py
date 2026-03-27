"""Dual-write persistence: MongoDB (source of truth) + Qdrant (search index)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from src.core.logger import get_logger
from src.rag.config import RAGConfig
from src.rag.protocols import (
    EmbeddingProvider,
    SparseEncoder,
    VectorStore,
    NodeRepository,
)

log = get_logger("rag.persistence")


class NodePersistenceService:
    def __init__(
        self,
        node_repo: NodeRepository,
        vector_store: VectorStore,
        embedder: EmbeddingProvider,
        sparse_encoder: SparseEncoder,
        config: RAGConfig,
    ):
        self.node_repo = node_repo
        self.vector_store = vector_store
        self.embedder = embedder
        self.sparse_encoder = sparse_encoder
        self.config = config

    async def persist_node(
        self,
        node: dict,
        *,
        session_id: str,
        market: str,
        date: str,
    ) -> None:
        """Write node to MongoDB first (must succeed), then index to Qdrant as background task."""
        import asyncio

        doc = self._build_doc(node, session_id=session_id, market=market, date=date)

        # MongoDB write — must succeed
        doc["indexed"] = False
        await self.node_repo.insert(doc)

        # Qdrant indexing — fire-and-forget; failure leaves indexed=False for reconciliation
        asyncio.create_task(self._background_index(doc))

    async def _background_index(self, doc: dict) -> None:
        """Index a doc to Qdrant in the background. Exceptions are logged, not propagated."""
        try:
            await self._index_doc(doc)
            await self.node_repo.mark_indexed(doc["id"], True)
        except Exception as e:
            log.warning("Background index failed for node %s: %s", doc["id"], e)

    async def persist_batch(
        self,
        nodes: list[dict],
        *,
        session_id: str,
        market: str,
        date: str,
    ) -> None:
        """Persist multiple nodes concurrently with bounded concurrency."""
        import asyncio

        sem = asyncio.Semaphore(5)

        async def _limited(node: dict) -> None:
            async with sem:
                await self.persist_node(
                    node, session_id=session_id, market=market, date=date
                )

        await asyncio.gather(*[_limited(n) for n in nodes])

    async def reconcile(self) -> int:
        """Find unindexed nodes in MongoDB and re-attempt Qdrant indexing."""
        import asyncio

        unindexed = await self.node_repo.find_unindexed()
        if not unindexed:
            return 0

        async def _reconcile_one(doc: dict) -> bool:
            try:
                await self._index_doc(doc)
                await self.node_repo.mark_indexed(doc["id"], True)
                return True
            except Exception as e:
                log.warning("Reconcile failed for node %s: %s", doc["id"], e)
                return False

        results = await asyncio.gather(*(_reconcile_one(d) for d in unindexed))
        return sum(results)

    async def prune(self) -> int:
        """Remove nodes older than prune_max_age_days from both stores.

        Order: collect IDs → delete from vector store → delete from MongoDB.
        This avoids orphaned Qdrant points if MongoDB delete fails.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self.config.prune_max_age_days
        )

        stale_ids = await self.node_repo.find_ids_older_than(cutoff)
        if not stale_ids:
            return 0

        # Best-effort vector store cleanup — don't let Qdrant failure block MongoDB prune
        try:
            await self.vector_store.delete(self.config.collection_name, stale_ids)
        except Exception as e:
            log.warning("Vector store delete failed during prune: %s", e)

        deleted_count = await self.node_repo.delete_older_than(cutoff)
        return deleted_count

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_doc(
        self,
        node: dict,
        *,
        session_id: str,
        market: str,
        date: str,
    ) -> dict:
        """Flatten a ThinkingNode dict into a node_store document."""
        return {
            "id": node["id"],
            "session_id": session_id,
            "type": node["type"],
            "layer": node.get("layer", 0),
            "content": node.get("content", ""),
            "reasoning": node.get("reasoning", ""),
            "confidence": node.get("confidence", 50),
            "parents": node.get("parents", []),
            "sources": node.get("sources", []),
            "sector": node.get("metadata", {}).get("sector"),
            "market": market,
            "date": date,
            "created_at": datetime.now(timezone.utc),
            "indexed": False,
        }

    async def _index_doc(self, doc: dict) -> None:
        """Compute dense + sparse embeddings and upsert a single point to Qdrant."""
        text = f"{doc.get('content', '')} {doc.get('reasoning', '')}"
        dense = await self.embedder.embed(text)
        sparse_indices, sparse_values = self.sparse_encoder.encode(text)

        point = {
            "id": doc["id"],
            "vector": {
                "dense": dense,
                "sparse": (sparse_indices, sparse_values),
            },
            "payload": {
                "node_type": doc["type"],
                "sector": doc.get("sector"),
                "confidence": doc.get("confidence", 50),
                "layer": doc.get("layer", 0),
                "market": doc.get("market"),
                "date": f"{doc.get('date') or '2020-01-01'}T00:00:00Z",
                "session_id": doc.get("session_id"),
                "content": doc.get("content", ""),
                "reasoning": doc.get("reasoning", ""),
            },
        }
        await self.vector_store.upsert(self.config.collection_name, [point])
