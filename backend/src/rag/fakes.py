"""Fake implementations for testing. No network, no Docker, deterministic."""

from __future__ import annotations

import hashlib
import struct
from datetime import datetime

from src.rag.protocols import (
    EmbeddingProvider,
    NodeRepository,
    SparseEncoder,
    VectorStore,
)


class FakeEmbedding:
    """Deterministic embeddings from text hash. No API calls."""

    def __init__(self, dim: int = 1024):
        self.dim = dim

    async def embed(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        values = []
        for i in range(self.dim):
            seed_bytes = hashlib.sha256(h + struct.pack(">I", i)).digest()[:4]
            # Use unsigned int mapped to [-1, 1] — avoids NaN/Inf from float bit patterns
            uint_val = struct.unpack(">I", seed_bytes)[0]
            val = (uint_val / 2147483647.5) - 1.0  # maps [0, 2^32-1] → [-1.0, ~1.0]
            values.append(float(val))
        return values

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(t) for t in texts]


class FakeSparseEncoder:
    """Word-split BM25-like sparse encoding. No model needed."""

    def encode(self, text: str) -> tuple[list[int], list[float]]:
        tokens = text.lower().split()
        if not tokens:
            return [], []
        indices = [abs(hash(t)) % 50000 for t in tokens]
        values = [1.0] * len(tokens)
        return indices, values


class FakeVectorStore:
    """In-memory vector store with brute-force search and payload filtering."""

    def __init__(self):
        self.points: dict[str, dict] = {}

    async def upsert(self, collection: str, points: list[dict]) -> None:
        for p in points:
            self.points[p["id"]] = p

    async def query(
        self,
        collection: str,
        dense: list[float],
        sparse: tuple[list[int], list[float]],
        filters: dict,
        limit: int,
    ) -> list[dict]:
        results = []
        for pid, point in self.points.items():
            payload = point.get("payload", {})
            if not self._matches_filters(payload, filters):
                continue
            score = self._dot(dense, point["vector"]["dense"])
            results.append({"id": pid, "score": score, **payload})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    async def delete(self, collection: str, ids: list[str]) -> None:
        for id_ in ids:
            self.points.pop(id_, None)

    def _matches_filters(self, payload: dict, filters: dict) -> bool:
        for key, value in filters.items():
            if key == "exclude_session_id":
                if payload.get("session_id") == value:
                    return False
            elif key == "min_confidence":
                if payload.get("confidence", 0) < value:
                    return False
            elif key == "date_from":
                if payload.get("date", "") < value:
                    return False
            elif key == "date_to":
                if payload.get("date", "9999") > value:
                    return False
            elif isinstance(value, list):
                if payload.get(key) not in value:
                    return False
            else:
                if payload.get(key) != value:
                    return False
        return True

    @staticmethod
    def _dot(a: list[float], b: list[float]) -> float:
        min_len = min(len(a), len(b))
        return sum(a[i] * b[i] for i in range(min_len))


class FakeNodeRepo:
    """In-memory MongoDB replacement."""

    def __init__(self):
        self.docs: dict[str, dict] = {}

    async def insert(self, doc: dict) -> None:
        self.docs[doc["id"]] = dict(doc)

    async def get(self, node_id: str) -> dict | None:
        return self.docs.get(node_id)

    async def find_unindexed(self) -> list[dict]:
        return [d for d in self.docs.values() if not d.get("indexed", True)]

    async def delete_older_than(self, cutoff: datetime) -> int:
        to_delete = [
            id_
            for id_, d in self.docs.items()
            if d.get("created_at") and d["created_at"] < cutoff
        ]
        for id_ in to_delete:
            del self.docs[id_]
        return len(to_delete)

    async def mark_indexed(self, node_id: str, indexed: bool) -> None:
        if node_id in self.docs:
            self.docs[node_id]["indexed"] = indexed

    async def find_ids_older_than(self, cutoff: datetime) -> list[str]:
        return [
            id_
            for id_, d in self.docs.items()
            if d.get("created_at") and d["created_at"] < cutoff
        ]
