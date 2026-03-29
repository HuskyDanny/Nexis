"""Protocol definitions for RAG services. Depend on these, not concrete classes."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class SparseEncoder(Protocol):
    def encode(self, text: str) -> tuple[list[int], list[float]]: ...


@runtime_checkable
class VectorStore(Protocol):
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
    async def insert(self, doc: dict) -> None: ...

    async def get(self, node_id: str) -> dict | None: ...

    async def find_unindexed(self) -> list[dict]: ...

    async def delete_older_than(self, cutoff: datetime) -> int: ...

    async def mark_indexed(self, node_id: str, indexed: bool) -> None: ...

    async def find_ids_older_than(self, cutoff: datetime) -> list[str]: ...
