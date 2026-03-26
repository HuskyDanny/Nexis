"""Benchmark fixtures — seeded vector store with known nodes."""

import pytest

from src.rag.config import RAGConfig
from src.rag.fakes import FakeEmbedding, FakeSparseEncoder, FakeVectorStore
from src.rag.search import NodeSearchService
from tests.benchmark.rag.golden_set import SEED_NODES


@pytest.fixture
def rag_config():
    return RAGConfig()


@pytest.fixture
def fake_embedding():
    return FakeEmbedding(dim=1024)


@pytest.fixture
def fake_sparse():
    return FakeSparseEncoder()


@pytest.fixture
async def seeded_store(fake_embedding, fake_sparse):
    store = FakeVectorStore()
    for node in SEED_NODES:
        text = f"{node['content']} {node['reasoning']}"
        dense = await fake_embedding.embed(text)
        indices, values = fake_sparse.encode(text)
        await store.upsert(
            "nodes",
            [
                {
                    "id": node["id"],
                    "vector": {"dense": dense, "sparse": (indices, values)},
                    "payload": node,
                }
            ],
        )
    return store


@pytest.fixture
def search_service(seeded_store, fake_embedding, fake_sparse, rag_config):
    return NodeSearchService(seeded_store, fake_embedding, fake_sparse, rag_config)
