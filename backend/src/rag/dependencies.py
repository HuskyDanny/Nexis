"""Composition root — wires concrete implementations together."""

from __future__ import annotations

import logging

from src.core.config import settings
from src.database.mongodb import mongodb
from src.rag.config import RAGConfig
from src.rag.embedding import SiliconFlowEmbedding
from src.rag.sparse_encoder import FastEmbedBM25
from src.rag.qdrant_store import QdrantVectorStore
from src.rag.node_store_repo import MongoNodeStoreRepo
from src.rag.persistence import NodePersistenceService
from src.rag.search import NodeSearchService

log = logging.getLogger("rag")

_rag_config: RAGConfig | None = None
_persistence: NodePersistenceService | None = None
_search: NodeSearchService | None = None
_qdrant: QdrantVectorStore | None = None


def get_rag_config() -> RAGConfig:
    global _rag_config
    if _rag_config is None:
        _rag_config = RAGConfig()
    return _rag_config


async def init_rag_services() -> tuple[NodePersistenceService, NodeSearchService]:
    global _persistence, _search, _qdrant

    config = get_rag_config()
    embedder = SiliconFlowEmbedding(model=config.embedding_model)
    sparse = FastEmbedBM25()

    _qdrant = QdrantVectorStore(url=settings.qdrant_url, config=config)
    await _qdrant.ensure_collection("nodes")

    node_repo = MongoNodeStoreRepo(mongodb.get_collection("node_store"))
    await node_repo.ensure_indexes()

    _persistence = NodePersistenceService(node_repo, _qdrant, embedder, sparse, config)
    _search = NodeSearchService(_qdrant, embedder, sparse, config)

    if config.reconcile_on_startup:
        count = await _persistence.reconcile()
        if count:
            log.info("Reconciled %d unindexed nodes", count)

    return _persistence, _search


def get_persistence() -> NodePersistenceService:
    if _persistence is None:
        raise RuntimeError(
            "RAG services not initialized. Call init_rag_services() first."
        )
    return _persistence


def get_search() -> NodeSearchService:
    if _search is None:
        raise RuntimeError(
            "RAG services not initialized. Call init_rag_services() first."
        )
    return _search


async def close_rag_services() -> None:
    global _qdrant
    if _qdrant:
        await _qdrant.close()
        _qdrant = None
