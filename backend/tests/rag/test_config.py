"""Tests for RAG configuration."""

import os
from unittest.mock import patch

from src.rag.config import RAGConfig


class TestRAGConfig:
    def test_defaults(self):
        config = RAGConfig()
        assert config.embedding_model == "BAAI/bge-m3"
        assert config.embedding_dim == 1024
        assert config.default_limit == 20
        assert config.prefetch_limit == 40
        assert config.decay_half_life_effect == 7.0
        assert config.decay_half_life_news == 3.0
        assert config.prune_max_age_days == 90

    def test_env_override(self):
        with patch.dict(os.environ, {"RAG_DECAY_HALF_LIFE_EFFECT": "3.0"}):
            config = RAGConfig()
            assert config.decay_half_life_effect == 3.0

    def test_half_life_map(self):
        config = RAGConfig()
        hl = config.half_life_map
        assert hl["news"] == 3.0
        assert hl["effect"] == 7.0
        assert hl["opportunity"] == 5.0
        assert hl["fetch"] == 3.0
