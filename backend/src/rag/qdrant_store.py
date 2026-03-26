"""Qdrant vector store implementation."""

from __future__ import annotations

import logging

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    HnswConfigDiff,
    OptimizersConfigDiff,
    PointStruct,
    SparseVector,
    Filter,
    FieldCondition,
    MatchAny,
    MatchValue,
    Range,
    MatchExcept,
    FusionQuery,
    Fusion,
    Prefetch,
)

from src.rag.config import RAGConfig

log = logging.getLogger("rag.qdrant")


class QdrantVectorStore:
    def __init__(self, url: str, config: RAGConfig):
        self.client = AsyncQdrantClient(url=url)
        self.config = config

    async def ensure_collection(self, collection: str) -> None:
        collections = await self.client.get_collections()
        existing = [c.name for c in collections.collections]
        if collection in existing:
            return
        await self.client.create_collection(
            collection_name=collection,
            vectors_config={
                "dense": VectorParams(
                    size=self.config.embedding_dim, distance=Distance.COSINE
                ),
            },
            sparse_vectors_config={"sparse": SparseVectorParams()},
            hnsw_config=HnswConfigDiff(
                m=self.config.hnsw_m, ef_construct=self.config.hnsw_ef_construct
            ),
            optimizers_config=OptimizersConfigDiff(
                deleted_threshold=0.2, vacuum_min_vector_number=1000
            ),
        )
        for field in ["node_type", "sector", "market", "session_id", "date"]:
            await self.client.create_payload_index(
                collection_name=collection, field_name=field, field_schema="keyword"
            )
        for field in ["confidence", "layer"]:
            await self.client.create_payload_index(
                collection_name=collection, field_name=field, field_schema="integer"
            )
        log.info("Created Qdrant collection '%s'", collection)

    async def upsert(self, collection: str, points: list[dict]) -> None:
        qdrant_points = []
        for p in points:
            sparse_data = p["vector"]["sparse"]
            qdrant_points.append(
                PointStruct(
                    id=p["id"],
                    vector={
                        "dense": p["vector"]["dense"],
                        "sparse": SparseVector(
                            indices=sparse_data[0], values=sparse_data[1]
                        ),
                    },
                    payload=p["payload"],
                )
            )
        await self.client.upsert(collection_name=collection, points=qdrant_points)

    async def query(
        self,
        collection: str,
        dense: list[float],
        sparse: tuple[list[int], list[float]],
        filters: dict,
        limit: int,
    ) -> list[dict]:
        qdrant_filter = self._build_filter(filters)
        results = await self.client.query_points(
            collection_name=collection,
            prefetch=[
                Prefetch(query=dense, using="dense", limit=limit),
                Prefetch(
                    query=SparseVector(indices=sparse[0], values=sparse[1]),
                    using="sparse",
                    limit=limit,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True,
        )
        return [
            {"id": str(pt.id), "score": pt.score, **(pt.payload or {})}
            for pt in results.points
        ]

    async def delete(self, collection: str, ids: list[str]) -> None:
        if not ids:
            return
        await self.client.delete(collection_name=collection, points_selector=ids)

    async def close(self) -> None:
        await self.client.close()

    @staticmethod
    def _build_filter(filters: dict) -> Filter | None:
        conditions = []
        for key, value in filters.items():
            if key == "exclude_session_id":
                conditions.append(
                    FieldCondition(
                        key="session_id", match=MatchExcept(**{"except": [value]})
                    )
                )
            elif key == "min_confidence":
                conditions.append(
                    FieldCondition(key="confidence", range=Range(gte=value))
                )
            elif key == "date_from":
                conditions.append(FieldCondition(key="date", range=Range(gte=value)))
            elif key == "date_to":
                conditions.append(FieldCondition(key="date", range=Range(lte=value)))
            elif isinstance(value, list):
                conditions.append(FieldCondition(key=key, match=MatchAny(any=value)))
            else:
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
        return Filter(must=conditions) if conditions else None
