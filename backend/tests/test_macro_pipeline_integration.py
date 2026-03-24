"""Integration test: full pipeline with macro news scoring and tiered quota."""

import pytest
from datetime import datetime, timezone
from src.pipelines.news.score import NewsDecayScore
from src.pipelines.news.quota import apply_tiered_quota


def _make_news(id: str, scope: int, sources: int = 1, cluster: int = 1):
    return {
        "id": id,
        "title": f"News {id}",
        "scope": scope,
        "story_cluster_size": cluster,
        "sources": [f"s{i}" for i in range(sources)],
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }


def test_macro_news_dominates_pool():
    scorer = NewsDecayScore()
    macro_items = [
        _make_news("geo-1", scope=5, sources=5, cluster=30),
        _make_news("geo-2", scope=5, sources=3, cluster=20),
        _make_news("macro-1", scope=4, sources=2, cluster=10),
    ]
    company_items = [
        _make_news("co-1", scope=1, sources=2, cluster=1),
        _make_news("co-2", scope=1, sources=1, cluster=1),
        _make_news("co-3", scope=2, sources=1, cluster=1),
        _make_news("co-4", scope=2, sources=1, cluster=1),
    ]
    all_items = macro_items + company_items
    for item in all_items:
        sr = scorer.score(item)
        item["score"] = sr.score

    macro_scores = [i["score"] for i in macro_items]
    company_scores = [i["score"] for i in company_items]
    assert min(macro_scores) > max(company_scores)

    pool = apply_tiered_quota(all_items, macro_ratio=0.4)
    # With 7 items and macro_ratio=0.4, macro_slots = int(7 * 0.4) = 2.
    # Guaranteed macro items occupy the first macro_slots positions.
    total = len(all_items)
    macro_slots = int(total * 0.4)
    guaranteed_macro = pool[:macro_slots]
    assert all(
        i["scope"] >= 4 for i in guaranteed_macro
    ), f"First {macro_slots} items must be macro-scope; got {[i['id'] for i in guaranteed_macro]}"
    # The remaining macro items (overflow) are appended after other slots.
    # Confirm all macro items still appear somewhere in the pool.
    pool_ids = {i["id"] for i in pool}
    for item in macro_items:
        assert item["id"] in pool_ids, f"Macro item {item['id']} missing from pool"


def test_scoring_no_ticker_penalty():
    scorer = NewsDecayScore()
    news_no_tickers = _make_news("geo", scope=5, sources=3, cluster=15)
    news_no_tickers["tickers"] = []
    news_with_tickers = _make_news("co", scope=1, sources=3, cluster=1)
    news_with_tickers["tickers"] = ["AAPL", "MSFT"]

    assert scorer.score(news_no_tickers).score > scorer.score(news_with_tickers).score
