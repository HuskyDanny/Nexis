# Tasks 4-6: Fetch Sources (NewsAPI + Perigon Stories + Composite)

Back to [[2026-03-24-macro-news-pipeline]]

---

### Task 4: NewsAPI Client

**Files:**
- Create: `backend/src/services/newsapi.py`
- Test: `backend/tests/test_newsapi_client.py`

- [ ] **Step 1: Write failing tests for NewsAPI normalization**

```python
# backend/tests/test_newsapi_client.py
from src.services.newsapi import _newsapi_to_pool_item, _infer_scope_from_title, _infer_sectors_from_title


def test_newsapi_to_pool_item_basic():
    article = {
        "title": "EU imposes new carbon tariffs on steel imports",
        "source": {"name": "Reuters"},
        "url": "https://reuters.com/article/123",
        "description": "The European Union announced...",
        "publishedAt": "2026-03-24T10:00:00Z",
    }
    item = _newsapi_to_pool_item(article)
    assert item["id"].startswith("na-")
    assert item["origin"] == "newsapi"
    assert item["title"] == article["title"]
    assert item["source"] == "Reuters"
    assert item["story_cluster_size"] == 1


def test_newsapi_to_pool_item_truncates_summary():
    article = {
        "title": "Test",
        "source": {"name": "AP"},
        "url": "https://example.com",
        "description": "x" * 300,
        "publishedAt": "2026-03-24T10:00:00Z",
    }
    item = _newsapi_to_pool_item(article)
    assert len(item["summary"]) <= 200


def test_infer_scope_geopolitical():
    assert _infer_scope_from_title("NATO deploys troops to Baltic states") >= 4


def test_infer_scope_company():
    assert _infer_scope_from_title("Apple releases new iPhone model") <= 2


def test_infer_sectors_from_title():
    sectors = _infer_sectors_from_title("OPEC cuts oil production amid energy crisis")
    assert any("energy" in s.lower() for s in sectors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_newsapi_client.py -v`
Expected: FAIL — module `src.services.newsapi` does not exist

- [ ] **Step 3: Create NewsAPI client**

Create `backend/src/services/newsapi.py` with:
- `_GEO_KEYWORDS`, `_MACRO_KEYWORDS`, `_SECTOR_MAP` — keyword sets for classification
- `_infer_scope_from_title(title) -> int` — keyword-based scope 1-5
- `_infer_sectors_from_title(title) -> list[str]` — keyword-based sector detection
- `_newsapi_to_pool_item(article, origin="newsapi") -> dict` — normalizer
- Rate limit tracking: `newsapi_usage` collection in MongoDB
- Cache: `newsapi_cache` collection with same pattern as Perigon
- `fetch_newsapi_headlines(category, language, page_size, daily_limit) -> list[dict]`
- `fetch_newsapi_everything(query, sort_by, page_size, daily_limit) -> list[dict]`

Both use `httpx.AsyncClient`, check cache first, enforce daily limits, return normalized pool items.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_newsapi_client.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/newsapi.py backend/tests/test_newsapi_client.py
git commit -m "feat: NewsAPI client with headline + everything endpoints"
```

---

### Task 5: Perigon Stories Fetch + Broadened Categories

**Files:**
- Modify: `backend/src/services/perigon.py`
- Test: `backend/tests/test_perigon_stories.py`

- [ ] **Step 1: Write failing test for stories normalization**

```python
# backend/tests/test_perigon_stories.py
from src.services.perigon import _story_to_pool_item


def test_story_to_pool_item_basic():
    story = {
        "storyId": "abc123",
        "title": "China bans rare earth exports to US",
        "summary": "Beijing announced...",
        "numArticles": 42,
        "initialPublishedAt": "2026-03-24T08:00:00Z",
        "topics": [{"name": "Trade"}],
        "categories": [{"name": "World"}],
        "sentiment": {"positive": 0.1, "negative": 0.8},
    }
    item = _story_to_pool_item(story)
    assert item["id"].startswith("pg-story-")
    assert item["story_cluster_size"] == 42
    assert item["origin"] == "perigon"
    assert item["scope"] >= 4


def test_story_cluster_size_preserved():
    story = {
        "storyId": "xyz",
        "title": "Local city council vote",
        "summary": "...",
        "numArticles": 3,
        "initialPublishedAt": "2026-03-24T08:00:00Z",
        "topics": [],
        "categories": [],
        "sentiment": {},
    }
    item = _story_to_pool_item(story)
    assert item["story_cluster_size"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_perigon_stories.py -v`
Expected: FAIL — `_story_to_pool_item` does not exist

- [ ] **Step 3: Add `_story_to_pool_item` and `fetch_perigon_stories` to perigon.py**

Add to `backend/src/services/perigon.py`:
- `_story_to_pool_item(story) -> dict` — converts `/stories` response to pool format. Reuses existing `_classify_scope` for scope calculation. Stores `numArticles` as `story_cluster_size`. ID prefix: `pg-story-`.
- `fetch_perigon_stories(categories, size, source_group) -> list[dict]` — hits `/v1/stories` endpoint with broad categories `["Politics", "World", "Environment", "Business", "Science"]`, `excludeLabel=["Opinion", "Non-news", "Paid News"]`, sorts by cluster size descending. Uses same cache/rate-limit pattern as `fetch_perigon_news`.

Also broaden the default query in existing `fetch_perigon_news`:
```python
query: str = "economy markets geopolitical trade climate policy"
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_perigon_stories.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/perigon.py backend/tests/test_perigon_stories.py
git commit -m "feat: Perigon /stories endpoint + broadened categories"
```

---

### Task 6: Composite Fetch + Pipeline Wiring

**Files:**
- Rewrite: `backend/src/pipelines/news/fetch.py`
- Modify: `backend/src/cron/scheduler.py`
- Test: `backend/tests/test_composite_fetch.py`

- [ ] **Step 1: Write failing test for CompositeFetch**

```python
# backend/tests/test_composite_fetch.py
import pytest
from src.pipelines.news.fetch import CompositeFetch


class FakeFetcher:
    def __init__(self, items: list[dict]):
        self._items = items

    async def fetch(self, market=None) -> list[dict]:
        return self._items


class FailingFetcher:
    async def fetch(self, market=None) -> list[dict]:
        raise RuntimeError("API down")


@pytest.mark.asyncio
async def test_composite_fetch_merges_results():
    f1 = FakeFetcher([{"id": "a"}])
    f2 = FakeFetcher([{"id": "b"}])
    cf = CompositeFetch([f1, f2])
    result = await cf.fetch()
    assert len(result) == 2


@pytest.mark.asyncio
async def test_composite_fetch_survives_failure():
    f1 = FakeFetcher([{"id": "a"}])
    f2 = FailingFetcher()
    cf = CompositeFetch([f1, f2])
    result = await cf.fetch()
    assert len(result) == 1
    assert result[0]["id"] == "a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_composite_fetch.py -v`
Expected: FAIL — `CompositeFetch` does not exist

- [ ] **Step 3: Rewrite fetch.py**

Replace `backend/src/pipelines/news/fetch.py` with:
- `CompositeFetch` — takes list of fetchers, calls each with graceful error handling
- `PerigonStoriesFetch` — wraps `fetch_perigon_stories()`
- `PerigonAllFetch` — wraps `fetch_perigon_news()`
- `NewsAPIHeadlinesFetch` — wraps `fetch_newsapi_headlines()`

All fetchers implement `async def fetch(self, market=None) -> list[dict]`.

- [ ] **Step 4: Update scheduler — single global news pipeline**

In `backend/src/cron/scheduler.py`:
- Update `build_news_pipeline()` — use `CompositeFetch([PerigonStoriesFetch(), PerigonAllFetch(), NewsAPIHeadlinesFetch()])`, pass `market=None`
- Update `run_news_pipeline()` — remove market loop, run once globally
- Update `_record_run` to accept `market: str | None`

- [ ] **Step 5: Run all tests**

Run: `cd backend && python -m pytest tests/test_composite_fetch.py tests/test_news_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/pipelines/news/fetch.py backend/src/cron/scheduler.py backend/tests/test_composite_fetch.py
git commit -m "feat: composite fetch (stories + all + newsapi) + global pipeline"
```
