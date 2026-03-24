from src.pipelines.news.quota import apply_tiered_quota


def test_tiered_quota_40_percent_macro():
    items = [{"id": f"macro-{i}", "scope": 5, "score": 90 - i} for i in range(3)] + [
        {"id": f"company-{i}", "scope": 1, "score": 80 - i} for i in range(7)
    ]
    result = apply_tiered_quota(items, macro_ratio=0.4)
    macro_count = sum(1 for r in result if r["scope"] >= 4)
    assert macro_count >= 3


def test_tiered_quota_fills_when_insufficient_macro():
    items = [
        {"id": "macro-1", "scope": 5, "score": 90},
    ] + [{"id": f"company-{i}", "scope": 1, "score": 80 - i} for i in range(9)]
    result = apply_tiered_quota(items, macro_ratio=0.4)
    assert len(result) == 10
    assert result[0]["id"] == "macro-1"


def test_tiered_quota_empty_list():
    assert apply_tiered_quota([], macro_ratio=0.4) == []


def test_tiered_quota_all_macro():
    items = [{"id": f"m-{i}", "scope": 5, "score": 90 - i} for i in range(5)]
    result = apply_tiered_quota(items, macro_ratio=0.4)
    assert len(result) == 5
