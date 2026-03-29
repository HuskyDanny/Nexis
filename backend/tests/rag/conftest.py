"""Shared fixtures for RAG tests."""

import pytest

from src.rag.config import RAGConfig
from src.rag.fakes import (
    FakeEmbedding,
    FakeNodeRepo,
    FakeSparseEncoder,
    FakeVectorStore,
)


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
def fake_store():
    return FakeVectorStore()


@pytest.fixture
def fake_repo():
    return FakeNodeRepo()
