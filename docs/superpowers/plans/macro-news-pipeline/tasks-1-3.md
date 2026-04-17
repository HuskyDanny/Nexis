# Tasks 1-3: Foundation (Model + Scoring + Pipeline Infrastructure)

Back to [[2026-03-24-macro-news-pipeline]]

---

### Task 1: Data Model + Config Changes

**Files:**
- Modify: `backend/src/models/news_entity.py`
- Modify: `backend/src/core/config.py`
- Test: `backend/tests/test_news_entity_model.py`

- [ ] **Step 1: Write failing test for new NewsEntity fields**

```python
# backend/tests/test_news_entity_model.py
from src.models.news_entity import NewsEntity


def test_news_entity_has_scope_field():
    e = NewsEntity(id="t1", canonical_title="Test", summary="s")
    assert e.scope == 2  # default


def test_news_entity_has_origin_field():
    e = NewsEntity(id="t1", canonical_title="Test", summary="s")
    assert e.origin == "perigon"


def test_news_entity_has_story_cluster_size():
    e = NewsEntity(id="t1", canonical_title="Test", summary="s")
    assert e.story_cluster_size == 1
```

**Note:** Do NOT remove `market` field yet — that happens in Task 3 alongside the pipeline infrastructure changes. Removing it here would break `test_fetch_placeholder_empty` and `_gen_id` before they're updated.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_news_entity_model.py -v`
Expected: FAIL — `scope`, `origin`, `story_cluster_size` not found

- [ ] **Step 3: Update NewsEntity model — add new fields only**

In `backend/src/models/news_entity.py`, add three new fields (keep `market` for now):

```python
class NewsEntity(BaseModel):
    id: str
    canonical_title: str
    summary: str
    sources: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    named_entities: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)
    scope: int = 2
    score: float = 0.0
    score_factors: dict[str, float] = Field(default_factory=dict)
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: EntityStatus = EntityStatus.ACTIVE
    market: str = "US"          # KEPT until Task 3
    origin: str = "perigon"
    story_cluster_size: int = 1
```

- [ ] **Step 4: Update config with new fields**

In `backend/src/core/config.py`, add to `Settings`:

```python
news_macro_quota_ratio: float = 0.4
newsapi_api_key: str = ""
newsapi_daily_limit: int = 100
newsapi_agent_daily_cap: int = 50
perigon_agent_daily_cap: int = 2
```

- [ ] **Step 5: Run ALL tests to verify no regressions**

Run: `cd backend && python -m pytest tests/test_news_entity_model.py tests/test_news_pipeline.py -v`
Expected: ALL PASS (new tests pass, existing tests unbroken)

- [ ] **Step 6: Commit**

```bash
git add backend/src/models/news_entity.py backend/src/core/config.py backend/tests/test_news_entity_model.py
git commit -m "feat: add scope/origin/cluster_size to NewsEntity"
```

---

### Task 2: Scoring Redesign

**Files:**
- Modify: `backend/src/pipelines/news/score.py`
- Modify: `backend/tests/test_news_pipeline.py`

- [ ] **Step 1: Write failing tests for new scoring formula**

Add to `backend/tests/test_news_pipeline.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_news_pipeline.py -v -k "macro_news or scope_factor or cluster_factor"`
Expected: FAIL

- [ ] **Step 3: Rewrite scoring formula**

Replace `backend/src/pipelines/news/score.py` with new formula:
- Weights: `0.4 * freshness + 0.25 * source_count + 0.2 * scope_factor + 0.15 * cluster_factor`
- `_scope_factor`: `scope / 5.0`
- `_cluster_factor`: `min(1.0, story_cluster_size / 20)`
- Remove `_ticker_factor` entirely

- [ ] **Step 4: Update `_entity` factory and existing tests**

In `backend/tests/test_news_pipeline.py`:

**a) Update `_entity()` factory** — add `scope` and `story_cluster_size` defaults:

```python
def _entity(age_days=0, sources=1, tickers=1, scope=2, story_cluster_size=1):
    dt = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    return {
        "first_seen_at": dt, "last_seen_at": dt,
        "sources": [f"s{i}" for i in range(sources)],
        "tickers": [f"T{i}" for i in range(tickers)],
        "scope": scope, "story_cluster_size": story_cluster_size,
    }
```

**b) Update these existing tests** (score ranges shifted due to new weights):

- `test_fresh_news_high_score` (line 19): Old formula gave ~68 for 1 source + 1 ticker. New formula: `0.4*1.0 + 0.25*0.4 + 0.2*0.4 + 0.15*0.05 = 0.5875 → 58.8`. Change assertion from `>= 60` to `>= 50`.
- `test_old_news_low_score` (line 25): Old threshold `< 30` still holds — freshness dominates decay. Keep as-is but verify.
- `test_multi_source_boost` (line 35): `source_count` factor unchanged in calculation, assertion `> 0.5` still holds. Keep as-is.
- `test_no_tickers` (line 40): Change from `r.factors.get("ticker_relevance", 0) == 0.0` to `assert "ticker_relevance" not in r.factors` and add `assert "scope_factor" in r.factors`.
- `test_fetch_placeholder_empty` (line 121): Import `AlphaVantageNewsFetch` will fail after Task 6 rewrites `fetch.py`. For now, leave as-is — it'll be updated in Task 6.

- [ ] **Step 5: Run all scoring tests**

Run: `cd backend && python -m pytest tests/test_news_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/pipelines/news/score.py backend/tests/test_news_pipeline.py
git commit -m "feat: scoring formula — scope_factor + cluster_factor replace ticker_relevance"
```

---

### Task 3: Pipeline Infrastructure (market-optional) + Remove market from NewsEntity

**Files:**
- Modify: `backend/src/models/news_entity.py` (remove `market` field)
- Modify: `backend/src/models/pool_common.py`
- Modify: `backend/src/pipelines/base.py`
- Modify: `backend/src/pipelines/news/process.py`
- Modify: `backend/src/database/repositories/news_entity_repo.py`
- Test: `backend/tests/test_news_pipeline.py`

- [ ] **Step 1: Write failing test for market-free ID generation**

Add to `backend/tests/test_news_pipeline.py`:

```python
def test_gen_id_no_market():
    """ID generation should not include market."""
    proc = HybridSimilarityProcess()
    raw = {"title": "Test headline", "date": "2026-03-24"}
    id1 = proc._gen_id(raw)
    raw_with_market = {"title": "Test headline", "date": "2026-03-24", "market": "CN"}
    id2 = proc._gen_id(raw_with_market)
    assert id1 == id2  # Market should not affect ID
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_news_pipeline.py::test_gen_id_no_market -v`
Expected: FAIL — IDs differ because current impl includes market in hash

- [ ] **Step 3: Update FetchStrategy protocol**

In `backend/src/models/pool_common.py`:

```python
@runtime_checkable
class FetchStrategy(Protocol):
    async def fetch(self, market: str | None = None) -> list[dict]: ...
```

- [ ] **Step 4: Update PoolPipeline — market optional**

In `backend/src/pipelines/base.py`, change `__init__` signature:

```python
def __init__(self, fetch, process, score, retain, repo, market: str | None = None):
```

And in `run()`:

```python
raw_items = await self.fetch.fetch(self.market)
existing = await self.repo.get_all(market=self.market, include_stale=True)
```

(These already pass `self.market`, which will now be `None` for news.)

- [ ] **Step 5: Update NewsEntityRepo — optional market**

In `backend/src/database/repositories/news_entity_repo.py`:

```python
async def get_active(self, market: str | None = None) -> list[dict]:
    q: dict = {"status": "active"}
    if market is not None:
        q["market"] = market
    cursor = self.collection.find(q, {"_id": 0})
    return await cursor.to_list(length=None)

async def get_all(self, market: str | None = None, include_stale: bool = False) -> list[dict]:
    q: dict = (
        {"status": {"$in": ["active", "stale"]}} if include_stale
        else {"status": "active"}
    )
    if market is not None:
        q["market"] = market
    return await self.collection.find(q, {"_id": 0}).to_list(length=None)
```

- [ ] **Step 6: Remove market from _gen_id**

In `backend/src/pipelines/news/process.py`:

```python
def _gen_id(self, raw: dict) -> str:
    title = raw.get("title", "")
    date = raw.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    return hashlib.sha256(f"{title}:{date}".encode()).hexdigest()[:16]
```

- [ ] **Step 7: Remove `market` field from NewsEntity**

In `backend/src/models/news_entity.py`, remove the `market: str = "US"` line that was kept in Task 1.

- [ ] **Step 8: Update `test_fetch_placeholder_empty`**

The `AlphaVantageNewsFetch` class will be replaced in Task 6. For now, update the test to use `market=None`:

```python
@pytest.mark.asyncio
async def test_fetch_placeholder_empty():
    r = await AlphaVantageNewsFetch().fetch(market=None)
    assert isinstance(r, list) and len(r) == 0
```

Also update `AlphaVantageNewsFetch.fetch` signature to accept optional market:

```python
class AlphaVantageNewsFetch:
    async def fetch(self, market: str | None = None) -> list[dict]:
        return []
```

- [ ] **Step 9: Add MongoDB index on `scope` field**

Add to the repo or a migration helper:

```python
# In news_entity_repo.py __init__ or a startup hook:
await self.collection.create_index("scope")
await self.collection.create_index("status")
```

- [ ] **Step 10: Run all tests**

Run: `cd backend && python -m pytest tests/test_news_pipeline.py tests/test_news_entity_model.py -v`
Expected: ALL PASS

- [ ] **Step 11: Commit**

```bash
git add backend/src/models/news_entity.py backend/src/models/pool_common.py backend/src/pipelines/base.py backend/src/pipelines/news/process.py backend/src/pipelines/news/fetch.py backend/src/database/repositories/news_entity_repo.py backend/tests/test_news_pipeline.py
git commit -m "feat: make market optional in pipeline, remove market from NewsEntity"
```
