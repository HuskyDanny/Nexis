"""Protocol definitions for graph services. Depend on these, not concrete classes."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class GraphStore(Protocol):
    """Abstract graph storage — swappable between Graphiti and fakes."""

    async def search(
        self,
        query: str,
        *,
        group_ids: list[str] | None = None,
        entity_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Semantic search with graph-augmented ranking.

        Returns list of dicts with keys:
            id, name, type, fact, score, source_entity, target_entity, related_facts
        """
        ...

    async def add_episode(
        self,
        name: str,
        body: str,
        source_description: str,
        *,
        group_id: str = "nexis",
        reference_time: datetime | None = None,
        entity_types: dict | None = None,
        edge_types: dict | None = None,
    ) -> str:
        """Ingest content as an episode. Returns episode ID."""
        ...

    async def get_entity(self, name: str) -> dict | None:
        """Get a single entity by name with its summary and edges."""
        ...

    async def get_neighbors(
        self,
        entity_name: str,
        *,
        edge_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get neighboring entities (1-hop)."""
        ...

    async def find_paths(
        self,
        source_name: str,
        target_name: str,
        *,
        max_hops: int = 4,
    ) -> list[dict]:
        """Find paths between two entities. Each dict has 'nodes' and 'edges' keys."""
        ...

    async def get_relationships(
        self,
        entity_name: str,
    ) -> list[dict]:
        """List all relationship types for an entity with counts."""
        ...

    async def run_cypher(
        self,
        query: str,
        params: dict | None = None,
    ) -> list[dict]:
        """Execute a read-only Cypher query. Max 100 rows, 5s timeout."""
        ...

    async def close(self) -> None:
        """Clean up connections."""
        ...
