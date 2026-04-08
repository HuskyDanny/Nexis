"""Centralized RAG configuration. All tunable parameters in one place.

DEPRECATED: Graph configuration is in src/graph/config.py.
This module is kept for backwards compatibility with existing tests.
"""

from pydantic_settings import BaseSettings


class RAGConfig(BaseSettings):
    """Override any parameter via env var with RAG_ prefix."""

    # Embedding
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024

    # Search
    dense_weight: float = 1.0
    sparse_weight: float = 1.0
    prefetch_limit: int = 40
    default_limit: int = 20

    # Decay half-lives (days)
    decay_half_life_news: float = 3.0
    decay_half_life_effect: float = 7.0
    decay_half_life_opportunity: float = 5.0
    decay_half_life_fetch: float = 3.0

    # Qdrant
    collection_name: str = "nodes"
    hnsw_m: int = 16
    hnsw_ef_construct: int = 100

    # Pruning
    prune_max_age_days: int = 90
    prune_interval_minutes: int = 30

    # Reconciliation
    reconcile_on_startup: bool = True
    reconcile_interval_minutes: int = 30

    # Retry
    index_retry_count: int = 2
    index_retry_delay_seconds: float = 1.0

    @property
    def half_life_map(self) -> dict[str, float]:
        return {
            "news": self.decay_half_life_news,
            "effect": self.decay_half_life_effect,
            "opportunity": self.decay_half_life_opportunity,
            "fetch": self.decay_half_life_fetch,
        }

    model_config = {"env_prefix": "RAG_"}
