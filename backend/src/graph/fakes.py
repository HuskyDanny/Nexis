"""In-memory fake GraphStore for unit testing. No Neo4j required."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid


class FakeGraphStore:
    """In-memory graph store implementing the GraphStore protocol."""

    def __init__(self) -> None:
        self.episodes: list[dict] = []
        self.entities: dict[str, dict] = {}  # name -> entity dict
        self.edges: list[dict] = []

    async def search(
        self,
        query: str,
        *,
        group_ids: list[str] | None = None,
        entity_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Simple substring match on edge facts and entity names."""
        query_lower = query.lower()

        matching_edges = [
            e for e in self.edges if query_lower in e.get("fact", "").lower()
        ][:limit]

        matching_nodes = [
            e
            for e in self.entities.values()
            if query_lower in e.get("name", "").lower()
            or query_lower in e.get("summary", "").lower()
        ][:limit]

        return [{"edges": matching_edges, "nodes": matching_nodes}]

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
        """Store episode and extract simple entities from body."""
        episode = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "body": body,
            "source_description": source_description,
            "group_id": group_id,
            "reference_time": (
                reference_time or datetime.now(timezone.utc)
            ).isoformat(),
        }
        self.episodes.append(episode)
        return episode["id"]

    async def get_entity(self, name: str) -> dict | None:
        """Exact name lookup."""
        return self.entities.get(name)

    async def get_neighbors(
        self,
        entity_name: str,
        *,
        edge_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Find edges where entity is source or target."""
        neighbors = []
        for edge in self.edges:
            if (
                edge.get("source_name") == entity_name
                or edge.get("target_name") == entity_name
            ):
                if edge_types and edge.get("edge_type") not in edge_types:
                    continue
                neighbors.append(edge)
                if len(neighbors) >= limit:
                    break
        return neighbors

    async def find_paths(
        self,
        source_name: str,
        target_name: str,
        *,
        max_hops: int = 4,
    ) -> list[dict]:
        """Simple BFS path finding on in-memory edges."""
        if source_name not in self.entities or target_name not in self.entities:
            return []

        # BFS
        visited: set[str] = {source_name}
        queue: list[tuple[str, list[dict], list[dict]]] = [
            (source_name, [self.entities[source_name]], [])
        ]

        paths = []
        while queue and len(paths) < 5:
            current, node_path, edge_path = queue.pop(0)
            if len(node_path) > max_hops + 1:
                continue

            for edge in self.edges:
                neighbor = None
                if edge.get("source_name") == current:
                    neighbor = edge.get("target_name")
                elif edge.get("target_name") == current:
                    neighbor = edge.get("source_name")

                if neighbor is None or neighbor in visited:
                    continue

                new_nodes = node_path + [
                    self.entities.get(neighbor, {"name": neighbor})
                ]
                new_edges = edge_path + [edge]

                if neighbor == target_name:
                    paths.append({"nodes": new_nodes, "edges": new_edges})
                else:
                    visited.add(neighbor)
                    queue.append((neighbor, new_nodes, new_edges))

        return paths

    async def get_relationships(
        self,
        entity_name: str,
    ) -> list[dict]:
        """Count edge types for an entity."""
        type_counts: dict[str, list[str]] = {}
        for edge in self.edges:
            if (
                edge.get("source_name") == entity_name
                or edge.get("target_name") == entity_name
            ):
                etype = edge.get("edge_type", "RELATES_TO")
                if etype not in type_counts:
                    type_counts[etype] = []
                type_counts[etype].append(edge.get("fact", ""))

        return [
            {
                "edge_type": etype,
                "count": len(facts),
                "sample_facts": facts[:3],
            }
            for etype, facts in type_counts.items()
        ]

    async def run_cypher(
        self,
        query: str,
        params: dict | None = None,
    ) -> list[dict]:
        """Not supported in fake — return empty."""
        return []

    async def close(self) -> None:
        """No-op."""
        pass

    # --- Test helpers ---

    def add_entity(self, name: str, entity_type: str = "Entity", **kwargs: Any) -> dict:
        """Helper: add an entity directly for testing."""
        entity = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "type": entity_type,
            "summary": kwargs.get("summary", ""),
            **kwargs,
        }
        self.entities[name] = entity
        return entity

    def add_edge(
        self,
        source_name: str,
        target_name: str,
        edge_type: str = "RELATES_TO",
        fact: str = "",
        **kwargs: Any,
    ) -> dict:
        """Helper: add an edge directly for testing."""
        edge = {
            "id": uuid.uuid4().hex[:12],
            "source_name": source_name,
            "target_name": target_name,
            "edge_type": edge_type,
            "fact": fact,
            **kwargs,
        }
        self.edges.append(edge)
        return edge
