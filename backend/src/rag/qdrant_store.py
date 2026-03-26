"""Qdrant vector store implementation."""

from __future__ import annotations

import uuid

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

from src.core.logger import get_logger
from src.rag.config import RAGConfig

log = get_logger("rag.qdrant")

# Namespace UUID for deterministic ID generation from string node IDs
_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _str_to_uuid(s: str) -> str:
    """Convert a string ID to a deterministic UUID string for Qdrant."""
    return str(uuid.uuid5(_NAMESPACE, s))


def _date_to_datetime_str(date_str: str) -> str:
    """Convert 'YYYY-MM-DD' to ISO datetime string for Qdrant datetime fields."""
    return f"{date_str}T00:00:00Z"


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
        for field in ["node_type", "sector", "market", "session_id"]:
            await self.client.create_payload_index(
                collection_name=collection, field_name=field, field_schema="keyword"
            )
        await self.client.create_payload_index(
            collection_name=collection, field_name="date", field_schema="datetime"
        )
        await self.client.create_payload_index(
            collection_name=collection, field_name="confidence", field_schema="float"
        )
        await self.client.create_payload_index(
            collection_name=collection, field_name="layer", field_schema="integer"
        )
        log.info("Created Qdrant collection '%s'", collection)

    async def upsert(self, collection: str, points: list[dict]) -> None:
        qdrant_points = []
        for p in points:
            sparse_data = p["vector"]["sparse"]
            payload = {**p["payload"], "_original_id": p["id"]}
            qdrant_points.append(
                PointStruct(
                    id=_str_to_uuid(p["id"]),
                    vector={
                        "dense": p["vector"]["dense"],
                        "sparse": SparseVector(
                            indices=sparse_data[0], values=sparse_data[1]
                        ),
                    },
                    payload=payload,
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
        out = []
        for pt in results.points:
            payload = dict(pt.payload or {})
            original_id = payload.pop("_original_id", str(pt.id))
            out.append({"id": original_id, "score": pt.score, **payload})
        return out

    async def delete(self, collection: str, ids: list[str]) -> None:
        if not ids:
            return
        uuid_ids = [_str_to_uuid(id_) for id_ in ids]
        await self.client.delete(collection_name=collection, points_selector=uuid_ids)

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
                conditions.append(
                    FieldCondition(
                        key="date",
                        range=Range(gte=_date_to_datetime_str(value)),
                    )
                )
            elif key == "date_to":
                conditions.append(
                    FieldCondition(
                        key="date",
                        range=Range(lte=_date_to_datetime_str(value)),
                    )
                )
            elif isinstance(value, list):
                conditions.append(FieldCondition(key=key, match=MatchAny(any=value)))
            else:
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
        return Filter(must=conditions) if conditions else None
