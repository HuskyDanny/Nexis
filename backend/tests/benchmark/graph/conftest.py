"""Benchmark fixtures — seeded graph store with known entities and edges."""

import pytest

from src.graph.fakes import FakeGraphStore
from tests.benchmark.graph.golden_set import SEED_ENTITIES, SEED_EDGES


@pytest.fixture
def graph_store():
    """FakeGraphStore seeded with golden set entities and edges."""
    store = FakeGraphStore()
    for entity in SEED_ENTITIES:
        store.add_entity(
            entity["name"],
            entity_type=entity.get("type", "Entity"),
            summary=entity.get("summary", ""),
            id=entity["id"],
        )
    for edge in SEED_EDGES:
        store.add_edge(
            edge["source_name"],
            edge["target_name"],
            edge_type=edge.get("edge_type", "RELATES_TO"),
            fact=edge.get("fact", ""),
        )
    return store
