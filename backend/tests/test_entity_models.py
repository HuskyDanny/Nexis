from datetime import datetime, timezone
import pytest
from src.models.pool_common import ScoreResult, ProcessResult, PipelineResult
from src.models.news_entity import NewsEntity, EntityStatus
from src.models.value_entity import ValueEntity


# --- EntityStatus ---


def test_entity_status_values():
    assert EntityStatus.ACTIVE == "active"
    assert EntityStatus.STALE == "stale"
    assert EntityStatus.ARCHIVED == "archived"


# --- NewsEntity ---


def test_news_entity_defaults():
    entity = NewsEntity(id="n1", canonical_title="Test", summary="A test summary")
    assert entity.score == 0.0
    assert entity.status == EntityStatus.ACTIVE
    assert entity.sources == []
    assert entity.tickers == []
    assert entity.sectors == []
    assert entity.named_entities == []
    assert entity.embedding == []
    assert entity.score_factors == {}
    assert entity.scope == 2
    assert entity.origin == "perigon"
    assert entity.story_cluster_size == 1
    assert isinstance(entity.first_seen_at, datetime)
    assert isinstance(entity.last_seen_at, datetime)
    assert entity.first_seen_at.tzinfo is not None
    assert entity.last_seen_at.tzinfo is not None


def test_news_entity_with_score():
    entity = NewsEntity(
        id="n2",
        canonical_title="Market Update",
        summary="Fed raises rates",
        score=0.85,
        embedding=[0.1, 0.2, 0.3],
        tickers=["AAPL", "MSFT"],
        score_factors={"recency": 0.9, "relevance": 0.8},
    )
    assert entity.score == 0.85
    assert entity.embedding == [0.1, 0.2, 0.3]
    assert entity.tickers == ["AAPL", "MSFT"]
    assert entity.score_factors == {"recency": 0.9, "relevance": 0.8}


# --- ValueEntity ---


def test_value_entity_defaults():
    entity = ValueEntity(id="v1", ticker="AAPL", name="Apple Inc.", sector="Technology")
    assert entity.score == 0.0
    assert entity.status == EntityStatus.ACTIVE
    assert entity.price is None
    assert entity.pe_ratio is None
    assert entity.market_cap is None
    assert entity.cash_flow is None
    assert entity.price_change_pct is None
    assert entity.score_factors == {}
    assert entity.market == "US"
    assert isinstance(entity.updated_at, datetime)
    assert entity.updated_at.tzinfo is not None


def test_value_entity_with_fundamentals():
    entity = ValueEntity(
        id="v2",
        ticker="NVDA",
        name="NVIDIA Corporation",
        sector="Semiconductors",
        price=875.50,
        pe_ratio=45.2,
        market_cap=2_150_000_000_000.0,
        cash_flow=8_000_000_000.0,
        price_change_pct=2.5,
        score=0.92,
        score_factors={"momentum": 0.95, "value": 0.89},
        market="US",
    )
    assert entity.price == 875.50
    assert entity.pe_ratio == 45.2
    assert entity.market_cap == 2_150_000_000_000.0
    assert entity.cash_flow == 8_000_000_000.0
    assert entity.price_change_pct == 2.5
    assert entity.score == 0.92
    assert entity.score_factors == {"momentum": 0.95, "value": 0.89}


# --- pool_common models ---


def test_score_result():
    result = ScoreResult(score=0.75, factors={"recency": 0.8, "volume": 0.7})
    assert result.score == 0.75
    assert result.factors == {"recency": 0.8, "volume": 0.7}


def test_process_result_insert():
    result = ProcessResult(action="insert", entity_id="n1")
    assert result.action == "insert"
    assert result.entity_id == "n1"
    assert result.merged_from is None


def test_process_result_merge():
    result = ProcessResult(action="merge", entity_id="n1", merged_from="n2")
    assert result.action == "merge"
    assert result.entity_id == "n1"
    assert result.merged_from == "n2"


def test_pipeline_result():
    result = PipelineResult(inserted=5, merged=2, rescored=10, removed=1)
    assert result.inserted == 5
    assert result.merged == 2
    assert result.rescored == 10
    assert result.removed == 1


def test_pipeline_result_defaults():
    result = PipelineResult()
    assert result.inserted == 0
    assert result.merged == 0
    assert result.rescored == 0
    assert result.removed == 0
