"""Tests for query-time decay scoring."""

import pytest
from datetime import datetime, timezone, timedelta

from src.rag.decay import decay_score
from src.rag.config import RAGConfig


@pytest.fixture
def config():
    return RAGConfig()


@pytest.fixture
def now():
    return datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)


class TestDecayScore:
    def test_zero_age_no_decay(self, config, now):
        score = decay_score(1.0, now, now, "effect", config)
        assert score == pytest.approx(1.0)

    def test_half_life_halves_score(self, config, now):
        node_date = now - timedelta(days=7)
        score = decay_score(1.0, node_date, now, "effect", config)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_double_half_life_quarters_score(self, config, now):
        node_date = now - timedelta(days=14)
        score = decay_score(1.0, node_date, now, "effect", config)
        assert score == pytest.approx(0.25, abs=0.01)

    def test_news_decays_faster(self, config, now):
        node_date = now - timedelta(days=5)
        news_score = decay_score(1.0, node_date, now, "news", config)
        effect_score = decay_score(1.0, node_date, now, "effect", config)
        assert news_score < effect_score

    def test_scales_with_relevance(self, config, now):
        node_date = now - timedelta(days=7)
        score_low = decay_score(0.5, node_date, now, "effect", config)
        score_high = decay_score(1.0, node_date, now, "effect", config)
        assert score_high == pytest.approx(2 * score_low, abs=0.01)

    def test_unknown_type_uses_default(self, config, now):
        node_date = now - timedelta(days=7)
        score = decay_score(1.0, node_date, now, "unknown_type", config)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_very_old_node_near_zero(self, config, now):
        node_date = now - timedelta(days=90)
        score = decay_score(1.0, node_date, now, "effect", config)
        assert score < 0.001

    def test_custom_half_life_via_config(self, now):
        config = RAGConfig(decay_half_life_effect=1.0)
        node_date = now - timedelta(days=1)
        score = decay_score(1.0, node_date, now, "effect", config)
        assert score == pytest.approx(0.5, abs=0.01)
