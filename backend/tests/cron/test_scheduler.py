"""Tests for cron scheduler pipeline factories.

PoolPipeline requires repo and market in its constructor, so the factories
accept market and repo as parameters and return a configured PoolPipeline.
"""

import pytest
from unittest.mock import MagicMock

from src.cron.scheduler import build_news_pipeline, build_value_pipeline
from src.pipelines.base import PoolPipeline


class TestBuildNewsPipeline:
    def _make_pipeline(self):
        mock_repo = MagicMock()
        return build_news_pipeline(repo=mock_repo)

    def test_returns_pool_pipeline(self):
        pipeline = self._make_pipeline()
        assert isinstance(pipeline, PoolPipeline)

    def test_has_fetch_strategy(self):
        pipeline = self._make_pipeline()
        assert hasattr(pipeline.fetch, "fetch")

    def test_has_process_strategy(self):
        pipeline = self._make_pipeline()
        assert hasattr(pipeline.process, "process")

    def test_has_score_strategy(self):
        pipeline = self._make_pipeline()
        assert hasattr(pipeline.score, "score")

    def test_has_retain_strategy(self):
        pipeline = self._make_pipeline()
        assert hasattr(pipeline.retain, "should_retain")

    def test_market_is_none(self):
        mock_repo = MagicMock()
        pipeline = build_news_pipeline(repo=mock_repo)
        assert pipeline.market is None


class TestBuildValuePipeline:
    def _make_pipeline(self):
        mock_repo = MagicMock()
        return build_value_pipeline(market="US", repo=mock_repo)

    def test_returns_pool_pipeline(self):
        pipeline = self._make_pipeline()
        assert isinstance(pipeline, PoolPipeline)

    def test_has_fetch_strategy(self):
        pipeline = self._make_pipeline()
        assert hasattr(pipeline.fetch, "fetch")

    def test_has_process_strategy(self):
        pipeline = self._make_pipeline()
        assert hasattr(pipeline.process, "process")

    def test_has_score_strategy(self):
        pipeline = self._make_pipeline()
        assert hasattr(pipeline.score, "score")

    def test_has_retain_strategy(self):
        pipeline = self._make_pipeline()
        assert hasattr(pipeline.retain, "should_retain")

    def test_market_is_set(self):
        mock_repo = MagicMock()
        pipeline = build_value_pipeline(market="CN", repo=mock_repo)
        assert pipeline.market == "CN"
