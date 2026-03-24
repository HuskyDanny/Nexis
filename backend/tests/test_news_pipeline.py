from datetime import datetime, timezone, timedelta
import pytest
from src.pipelines.news.score import NewsDecayScore
from src.pipelines.news.process import HybridSimilarityProcess
from src.pipelines.news.fetch import AlphaVantageNewsFetch


# --- NewsDecayScore ---
def _entity(age_days=0, sources=1, tickers=1, scope=2, story_cluster_size=1):
    dt = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    return {
        "first_seen_at": dt,
        "last_seen_at": dt,
        "sources": [f"s{i}" for i in range(sources)],
        "tickers": [f"T{i}" for i in range(tickers)],
        "scope": scope,
        "story_cluster_size": story_cluster_size,
    }


def test_fresh_news_high_score():
    # With sources=1, scope=2, cluster=1: raw = 0.4*1.0 + 0.25*0.4 + 0.2*0.4 + 0.15*0.05 = 0.5875 → score=58.8
    r = NewsDecayScore(half_life_days=3.0).score(_entity(age_days=0))
    assert r.score >= 50 and r.factors["freshness"] >= 0.9


def test_old_news_low_score():
    r = NewsDecayScore(half_life_days=3.0).score(_entity(age_days=10))
    assert r.score < 30 and r.factors["freshness"] < 0.15


def test_half_life_freshness():
    r = NewsDecayScore(half_life_days=3.0).score(_entity(age_days=3))
    assert 0.4 < r.factors["freshness"] < 0.6


def test_multi_source_boost():
    r = NewsDecayScore(half_life_days=3.0).score(_entity(sources=3, tickers=2))
    assert r.factors["source_count"] > 0.5


def test_no_tickers():
    r = NewsDecayScore(half_life_days=3.0).score(_entity(tickers=0))
    assert "ticker_relevance" not in r.factors
    assert "scope_factor" in r.factors


def test_macro_news_scores_higher_than_company_news():
    """Macro news (scope=5, cluster=25) should outscore company news (scope=1, cluster=1)."""
    scorer = NewsDecayScore()
    macro = _entity(age_days=1, sources=3, scope=5, story_cluster_size=25)
    company = _entity(age_days=1, sources=2, scope=1, story_cluster_size=1)
    company["tickers"] = ["AAPL"]
    assert scorer.score(macro).score > scorer.score(company).score


def test_scope_factor_in_score_factors():
    scorer = NewsDecayScore()
    e = _entity(age_days=0, sources=1, scope=4)
    result = scorer.score(e)
    assert "scope_factor" in result.factors
    assert "cluster_factor" in result.factors
    assert "ticker_relevance" not in result.factors


def test_cluster_factor_maxes_at_20():
    scorer = NewsDecayScore()
    e = _entity(age_days=0, sources=1, scope=3, story_cluster_size=50)
    result = scorer.score(e)
    assert result.factors["cluster_factor"] == 1.0


# --- HybridSimilarityProcess ---
@pytest.mark.asyncio
async def test_insert_no_existing():
    p = HybridSimilarityProcess(similarity_threshold=0.6)
    r = await p.process(
        {"title": "Fed holds rates", "tickers": ["SPY"], "named_entities": ["Fed"]},
        existing=[],
    )
    assert r.action == "insert" and r.entity_id != "" and r.merged_from is None


@pytest.mark.asyncio
async def test_insert_no_similar():
    p = HybridSimilarityProcess(similarity_threshold=0.6)
    r = await p.process(
        {
            "title": "Oil surge OPEC cuts",
            "tickers": ["USO"],
            "named_entities": ["OPEC"],
        },
        existing=[
            {
                "id": "e1",
                "canonical_title": "Fed holds rates",
                "tickers": ["SPY"],
                "named_entities": ["Fed"],
            }
        ],
    )
    assert r.action == "insert"


@pytest.mark.asyncio
async def test_merge_similar_title():
    p = HybridSimilarityProcess(similarity_threshold=0.5)
    r = await p.process(
        {
            "title": "Federal Reserve holds interest rates steady",
            "tickers": ["SPY"],
            "named_entities": ["Federal Reserve"],
        },
        existing=[
            {
                "id": "e_fed",
                "canonical_title": "Fed holds rates steady for March meeting",
                "tickers": ["SPY"],
                "named_entities": ["Federal Reserve"],
            }
        ],
    )
    assert r.action == "merge" and r.entity_id == "e_fed"


@pytest.mark.asyncio
async def test_merge_shared_entities():
    p = HybridSimilarityProcess(similarity_threshold=0.4)
    r = await p.process(
        {
            "title": "Completely different headline about rates",
            "tickers": ["SPY", "TLT"],
            "named_entities": ["Federal Reserve", "Jerome Powell"],
        },
        existing=[
            {
                "id": "e_fed",
                "canonical_title": "Fed signals rate pause",
                "tickers": ["SPY"],
                "named_entities": ["Federal Reserve", "Jerome Powell"],
            }
        ],
    )
    assert r.action == "merge" and r.entity_id == "e_fed"


# --- AlphaVantageNewsFetch ---
@pytest.mark.asyncio
async def test_fetch_placeholder_empty():
    r = await AlphaVantageNewsFetch().fetch(market="US")
    assert isinstance(r, list) and len(r) == 0
