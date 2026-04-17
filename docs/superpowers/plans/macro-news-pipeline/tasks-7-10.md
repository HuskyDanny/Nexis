# Tasks 7-10: Integration (Agent Tool + API Layer + Verification)

Back to [[2026-03-24-macro-news-pipeline]]

---

### Task 7: Agent `fetch_news` Tool

**Files:**
- Create: `backend/src/agents/tools/__init__.py`
- Create: `backend/src/agents/tools/fetch_news.py`
- Test: `backend/tests/test_fetch_news_tool.py`

- [ ] **Step 1: Write failing test for fetch_news tool**

```python
# backend/tests/test_fetch_news_tool.py
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.tools.fetch_news import FetchNewsTool


@pytest.mark.asyncio
async def test_fetch_news_returns_results():
    tool = FetchNewsTool()
    with patch("src.agents.tools.fetch_news.fetch_perigon_news", new_callable=AsyncMock) as mock_pg, \
         patch("src.agents.tools.fetch_news._has_api_budget", new_callable=AsyncMock) as mock_budget:
        mock_budget.return_value = True
        mock_pg.return_value = [{"id": "pg-123", "title": "Test news", "scope": 4}]
        results = await tool.arun(query="rare earth supply chain")
        assert len(results) == 1
        assert results[0]["id"] == "pg-123"


@pytest.mark.asyncio
async def test_fetch_news_fallback_when_no_budget():
    tool = FetchNewsTool()
    with patch("src.agents.tools.fetch_news._has_api_budget", new_callable=AsyncMock) as mock_budget, \
         patch("src.agents.tools.fetch_news._fallback_text_search", new_callable=AsyncMock) as mock_search:
        mock_budget.return_value = False
        mock_search.return_value = [{"id": "cached-1", "title": "Cached result"}]
        results = await tool.arun(query="rare earth")
        assert len(results) == 1
        mock_search.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_fetch_news_tool.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create agent tools package**

```python
# backend/src/agents/tools/__init__.py
"""Agent tools — callable tools for agent reasoning."""
```

- [ ] **Step 4: Create FetchNewsTool**

Create `backend/src/agents/tools/fetch_news.py` with:
- `_has_api_budget() -> bool` — checks `perigon_usage` and `newsapi_usage` against daily caps from config
- `_fallback_text_search(query, limit) -> list[dict]` — regex search on `canonical_title` in `news_entities` collection, sorted by score
- `FetchNewsTool(BaseTool)`:
  - `name = "fetch_news"`, description explains its purpose for the agent
  - `_run(query)` — sync wrapper using `asyncio.run()` for CrewAI compatibility
  - `arun(query)` — async impl: check budget → Perigon first → NewsAPI supplement → return results
  - `max_results: int = 5`

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_fetch_news_tool.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/agents/tools/__init__.py backend/src/agents/tools/fetch_news.py backend/tests/test_fetch_news_tool.py
git commit -m "feat: agent fetch_news tool — directed search with budget fallback"
```

---

### Task 8: Thinker Agent Integration

**Files:**
- Modify: `backend/src/agents/thinking_crew.py`

- [ ] **Step 1: Register FetchNewsTool in Thinker agent**

In `backend/src/agents/thinking_crew.py`:
- Add import: `from src.agents.tools.fetch_news import FetchNewsTool`
- In the `run_thinker` function, find where the Thinker `Agent(...)` or `Task(tools=[...])` is created
- Add `FetchNewsTool()` to the tools list

- [ ] **Step 2: Verify existing tests still pass**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: ALL existing tests PASS (no regressions)

- [ ] **Step 3: Commit**

```bash
git add backend/src/agents/thinking_crew.py
git commit -m "feat: register fetch_news tool in Thinker agent"
```

---

### Task 9: API Layer — Global Pool + Tiered Quota

**Files:**
- Create: `backend/src/pipelines/news/quota.py`
- Modify: `backend/src/api/pools.py`
- Modify: `backend/src/api/thinking.py`
- Test: `backend/tests/test_tiered_quota.py`

- [ ] **Step 1: Write failing test for tiered quota**

```python
# backend/tests/test_tiered_quota.py
from src.pipelines.news.quota import apply_tiered_quota


def test_tiered_quota_40_percent_macro():
    items = [
        {"id": f"macro-{i}", "scope": 5, "score": 90 - i} for i in range(3)
    ] + [
        {"id": f"company-{i}", "scope": 1, "score": 80 - i} for i in range(7)
    ]
    result = apply_tiered_quota(items, macro_ratio=0.4)
    macro_count = sum(1 for r in result if r["scope"] >= 4)
    assert macro_count >= 3  # All 3 macro items present


def test_tiered_quota_fills_when_insufficient_macro():
    items = [
        {"id": "macro-1", "scope": 5, "score": 90},
    ] + [
        {"id": f"company-{i}", "scope": 1, "score": 80 - i} for i in range(9)
    ]
    result = apply_tiered_quota(items, macro_ratio=0.4)
    assert len(result) == 10
    assert result[0]["id"] == "macro-1"  # Macro first


def test_tiered_quota_empty_list():
    assert apply_tiered_quota([], macro_ratio=0.4) == []


def test_tiered_quota_all_macro():
    items = [{"id": f"m-{i}", "scope": 5, "score": 90 - i} for i in range(5)]
    result = apply_tiered_quota(items, macro_ratio=0.4)
    assert len(result) == 5  # All returned, no crash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tiered_quota.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create quota module**

Create `backend/src/pipelines/news/quota.py`:

```python
def apply_tiered_quota(
    items: list[dict],
    macro_ratio: float = 0.4,
    macro_scope_threshold: int = 4,
) -> list[dict]:
    if not items:
        return []

    macro = [n for n in items if n.get("scope", 0) >= macro_scope_threshold]
    other = [n for n in items if n.get("scope", 0) < macro_scope_threshold]

    macro.sort(key=lambda x: x.get("score", 0), reverse=True)
    other.sort(key=lambda x: x.get("score", 0), reverse=True)

    total = len(items)
    macro_slots = min(int(total * macro_ratio), len(macro))
    other_slots = total - macro_slots

    return macro[:macro_slots] + other[:other_slots] + macro[macro_slots:]
```

- [ ] **Step 4: Run quota tests**

Run: `cd backend && python -m pytest tests/test_tiered_quota.py -v`
Expected: ALL PASS

- [ ] **Step 5: Update pools.py — global news, market for values only**

In `backend/src/api/pools.py`:
- Import: `from src.pipelines.news.quota import apply_tiered_quota`
- In `get_pools` endpoint: change news query from `{"market": market, "status": "active"}` to `{"status": "active"}`
- Apply `apply_tiered_quota(news_items)` before returning
- Keep value entities query with market filter unchanged

- [ ] **Step 6: Update thinking.py — replace legacy pool loading with entity-based loading**

**IMPORTANT:** `thinking.py` currently loads from the legacy `pools` collection (lines 69-77), NOT from `news_entities`. The change is bigger than just removing a market filter:

In `backend/src/api/thinking.py`:
- Import: `from src.pipelines.news.quota import apply_tiered_quota`
- Import: `from src.database.repositories.news_entity_repo import NewsEntityRepo`
- Replace the legacy pool loading block (lines 68-88):

```python
# BEFORE (legacy — loads from "pools" collection with snapshots):
pools_col = mongodb.get_collection("pools")
news_pool = await pools_col.find_one(
    {"type": "news", "date": req.date, "market": req.market}, {"_id": 0}
)
value_pool = await pools_col.find_one(
    {"type": "value", "date": req.date, "market": req.market}, {"_id": 0}
)
news_items = (news_pool or {}).get("items", [])
value_items = (value_pool or {}).get("items", [])

# AFTER (entity-based — reads living entities directly):
news_repo = NewsEntityRepo(mongodb.get_collection("news_entities"))
all_news = await news_repo.get_active()  # No market filter — global
news_items = apply_tiered_quota(
    sorted(all_news, key=lambda x: x.get("score", 0), reverse=True),
    macro_ratio=settings.news_macro_quota_ratio,
)

# Value pool: keep legacy path OR use value_entity_repo with market filter
value_col = mongodb.get_collection("pools")
value_pool = await value_col.find_one(
    {"type": "value", "date": req.date, "market": req.market}, {"_id": 0}
)
value_items = (value_pool or {}).get("items", [])
```

Keep `req.market` in `StartRequest` — it's used for value pool filtering only. The live fallback (`fetch_real_news`, `fetch_real_stocks`) also stays for when entities are empty.

- [ ] **Step 7: Run all tests**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add backend/src/pipelines/news/quota.py backend/src/api/pools.py backend/src/api/thinking.py backend/tests/test_tiered_quota.py
git commit -m "feat: global news pool with tiered quota — 40% macro guaranteed"
```

---

### Task 10: Integration Test + Full Pipeline Verification

**Files:**
- Create: `backend/tests/test_macro_pipeline_integration.py`

- [ ] **Step 1: Write integration test**

```python
# backend/tests/test_macro_pipeline_integration.py
"""Integration test: full pipeline with macro news scoring and tiered quota."""
import pytest
from datetime import datetime, timezone
from src.pipelines.news.score import NewsDecayScore
from src.pipelines.news.quota import apply_tiered_quota


def _make_news(id: str, scope: int, sources: int = 1, cluster: int = 1):
    return {
        "id": id, "title": f"News {id}", "scope": scope,
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
    top_3 = pool[:3]
    assert all(i["scope"] >= 4 for i in top_3)


def test_scoring_no_ticker_penalty():
    scorer = NewsDecayScore()
    news_no_tickers = _make_news("geo", scope=5, sources=3, cluster=15)
    news_no_tickers["tickers"] = []
    news_with_tickers = _make_news("co", scope=1, sources=3, cluster=1)
    news_with_tickers["tickers"] = ["AAPL", "MSFT"]

    assert scorer.score(news_no_tickers).score > scorer.score(news_with_tickers).score
```

- [ ] **Step 2: Run integration test**

Run: `cd backend && python -m pytest tests/test_macro_pipeline_integration.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v --timeout=60`
Expected: ALL PASS — no regressions

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_macro_pipeline_integration.py
git commit -m "test: integration test for macro news scoring + tiered quota"
```
