"""Graph service configuration."""

from __future__ import annotations

from pydantic import BaseModel


class GraphConfig(BaseModel):
    """Configuration for Graphiti/Neo4j graph services."""

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "nexis-dev-password"

    # LLM config (SiliconFlow OpenAI-compatible)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.siliconflow.cn/v1"
    llm_model: str = "Qwen/Qwen3.5-397B-A17B"
    llm_small_model: str = "Qwen/Qwen2.5-7B-Instruct"

    # Embedding config
    embedding_model: str = "BAAI/bge-m3"

    # Graphiti config
    group_id: str = "nexis"
    store_raw_episode_content: bool = True
