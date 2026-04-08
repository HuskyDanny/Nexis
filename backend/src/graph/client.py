"""Concrete GraphStore implementation wrapping graphiti-core."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.graph.config import GraphConfig

logger = logging.getLogger(__name__)


class GraphitiStore:
    """GraphStore implementation backed by Graphiti + Neo4j."""

    def __init__(self, config: GraphConfig) -> None:
        self._config = config
        self._graphiti: Any = None  # Lazy — avoids import at module level

    async def initialize(self) -> None:
        """Connect to Neo4j, initialize Graphiti, build indices."""
        from graphiti_core import Graphiti
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

        llm_client = OpenAIGenericClient(
            config=LLMConfig(
                api_key=self._config.llm_api_key,
                base_url=self._config.llm_base_url,
                model=self._config.llm_model,
                small_model=self._config.llm_small_model,
            )
        )
        embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                embedding_model=self._config.embedding_model,
                api_key=self._config.llm_api_key,
                base_url=self._config.llm_base_url,
            )
        )

        self._graphiti = Graphiti(
            self._config.neo4j_uri,
            self._config.neo4j_user,
            self._config.neo4j_password,
            llm_client=llm_client,
            embedder=embedder,
            store_raw_episode_content=self._config.store_raw_episode_content,
        )
        await self._graphiti.build_indices_and_constraints()
        logger.info("Graphiti initialized — Neo4j at %s", self._config.neo4j_uri)

    @property
    def graphiti(self) -> Any:
        if self._graphiti is None:
            raise RuntimeError(
                "GraphitiStore not initialized — call initialize() first"
            )
        return self._graphiti

    async def search(
        self,
        query: str,
        *,
        group_ids: list[str] | None = None,
        entity_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Hybrid search: BM25 + cosine + graph structure via Graphiti."""
        from graphiti_core.search.search_config_recipes import (
            COMBINED_HYBRID_SEARCH_RRF,
        )

        results = await self.graphiti.search_(
            query=query,
            config=COMBINED_HYBRID_SEARCH_RRF,
            group_ids=group_ids or [self._config.group_id],
            num_results=limit,
        )

        edges_out = []
        for edge in results.edges:
            edges_out.append(
                {
                    "id": edge.uuid,
                    "name": edge.name,
                    "fact": edge.fact,
                    "source_entity": edge.source_node_uuid,
                    "target_entity": edge.target_node_uuid,
                    "valid_at": edge.valid_at.isoformat() if edge.valid_at else None,
                    "invalid_at": (
                        edge.invalid_at.isoformat() if edge.invalid_at else None
                    ),
                }
            )

        nodes_out = []
        for node in results.nodes:
            node_dict = {
                "id": node.uuid,
                "name": node.name,
                "type": node.labels[0] if node.labels else "Entity",
                "summary": node.summary or "",
            }
            nodes_out.append(node_dict)

        return [{"edges": edges_out, "nodes": nodes_out}]

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
        """Ingest content as a Graphiti episode."""
        from graphiti_core.nodes import EpisodeType

        ref_time = reference_time or datetime.now(timezone.utc)
        await self.graphiti.add_episode(
            name=name,
            episode_body=body,
            source=EpisodeType.text,
            source_description=source_description,
            reference_time=ref_time,
            group_id=group_id,
            entity_types=entity_types,
            edge_types=edge_types,
        )
        return name

    async def get_entity(self, name: str) -> dict | None:
        """Find entity by name via search, return with summary."""
        from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

        results = await self.graphiti.search_(
            query=name,
            config=NODE_HYBRID_SEARCH_RRF,
            group_ids=[self._config.group_id],
            num_results=1,
        )
        if not results.nodes:
            return None
        node = results.nodes[0]
        return {
            "id": node.uuid,
            "name": node.name,
            "type": node.labels[0] if node.labels else "Entity",
            "summary": node.summary or "",
        }

    async def get_neighbors(
        self,
        entity_name: str,
        *,
        edge_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get 1-hop neighbors via Cypher."""
        type_filter = ""
        if edge_types:
            types_str = "|".join(edge_types)
            type_filter = f"AND type(r) IN ['{types_str}']"

        query = f"""
        MATCH (n:Entity)-[r]-(neighbor:Entity)
        WHERE n.name = $name {type_filter}
        RETURN neighbor.name AS name, neighbor.uuid AS id,
               labels(neighbor) AS labels, type(r) AS edge_type,
               r.fact AS fact, r.name AS edge_name,
               CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END AS direction
        LIMIT $limit
        """
        rows = await self.run_cypher(query, {"name": entity_name, "limit": limit})
        return rows

    async def find_paths(
        self,
        source_name: str,
        target_name: str,
        *,
        max_hops: int = 4,
    ) -> list[dict]:
        """Find shortest paths between two entities."""
        query = (
            """
        MATCH path = shortestPath(
            (a:Entity {name: $source})-[*..%d]-(b:Entity {name: $target})
        )
        RETURN [n IN nodes(path) | {name: n.name, id: n.uuid, labels: labels(n)}] AS nodes,
               [r IN relationships(path) | {type: type(r), fact: r.fact, name: r.name}] AS edges
        LIMIT 5
        """
            % max_hops
        )
        rows = await self.run_cypher(
            query, {"source": source_name, "target": target_name}
        )
        return [{"nodes": r["nodes"], "edges": r["edges"]} for r in rows]

    async def get_relationships(
        self,
        entity_name: str,
    ) -> list[dict]:
        """List relationship types and counts for an entity."""
        query = """
        MATCH (n:Entity {name: $name})-[r]-(:Entity)
        RETURN type(r) AS edge_type, r.name AS edge_name, count(*) AS count,
               collect(r.fact)[0..3] AS sample_facts
        ORDER BY count DESC
        """
        return await self.run_cypher(query, {"name": entity_name})

    async def run_cypher(
        self,
        query: str,
        params: dict | None = None,
    ) -> list[dict]:
        """Execute a read-only Cypher query."""
        # Guard: reject write operations
        upper = query.strip().upper()
        for keyword in ("CREATE", "MERGE", "DELETE", "SET ", "REMOVE ", "DROP "):
            if keyword in upper:
                raise ValueError(
                    f"Write operations not allowed in run_cypher: {keyword.strip()}"
                )

        driver = self.graphiti.clients.driver
        records, _, _ = await driver.execute_query(
            query,
            parameters_=params or {},
            routing_="r",
        )
        return [dict(r) for r in records]

    async def close(self) -> None:
        """Close Graphiti and Neo4j connections."""
        if self._graphiti:
            await self._graphiti.close()
            self._graphiti = None
            logger.info("Graphiti connections closed")
