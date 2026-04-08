"""Protocol definitions for RAG services.

DEPRECATED: Qdrant-based protocols (VectorStore, SparseEncoder, EmbeddingProvider)
are replaced by GraphStore from src.graph.protocols.

These protocols are kept for backwards compatibility with existing test code.
New code should depend on src.graph.protocols.GraphStore instead.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

# Re-export GraphStore so code can import from either location
from src.graph.protocols import GraphStore  # noqa: F401


@runtime_checkable
class EmbeddingProvider(Protocol):
    """DEPRECATED: Graph services handle embeddings internally."""

    async def embed(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class SparseEncoder(Protocol):
    """DEPRECATED: Graph services handle sparse encoding internally."""

    def encode(self, text: str) -> tuple[list[int], list[float]]: ...


@runtime_checkable
class VectorStore(Protocol):
    """DEPRECATED: Replaced by GraphStore protocol."""

    async def upsert(self, collection: str, points: list[dict]) -> None: ...

    async def query(
        self,
        collection: str,
        dense: list[float],
        sparse: tuple[list[int], list[float]],
        filters: dict,
        limit: int,
    ) -> list[dict]: ...

    async def delete(self, collection: str, ids: list[str]) -> None: ...


@runtime_checkable
class NodeRepository(Protocol):
    """DEPRECATED: Graph services handle node storage via Neo4j."""

    async def insert(self, doc: dict) -> None: ...

    async def get(self, node_id: str) -> dict | None: ...

    async def find_unindexed(self) -> list[dict]: ...

    async def delete_older_than(self, cutoff: datetime) -> int: ...

    async def mark_indexed(self, node_id: str, indexed: bool) -> None: ...

    async def find_ids_older_than(self, cutoff: datetime) -> list[str]: ...
