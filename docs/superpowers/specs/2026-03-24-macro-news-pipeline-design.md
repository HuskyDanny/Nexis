# Macro News Pipeline Redesign

**Date:** 2026-03-24
**Status:** Draft
**Problem:** The news pool is too narrow — dominated by company/ticker-specific financial news. Macro signals (geopolitics, climate, trade policy, resource shifts) are the *causes* that the Thinker agent needs to reason from, but the current fetch and scoring pipeline suppresses them.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Fetch strategy | Perigon `/stories` + `/all` + NewsAPI | Multiple sources for breadth; `/stories` clusters high-coverage events |
| Scoring | Replace `ticker_relevance` with `scope_factor` + `cluster_factor` | Stop penalizing ticker-less macro news |
| Pool structure | Tiered with 40% macro quota | Guarantee Thinker always has causal seeds |
| Market partition | Removed from news | News is global; market filter only on value pool |
| Agent fetch | `fetch_news` tool for directed search | Agent can actively pull evidence mid-reasoning |
| NewsAPI tier | Free (24h delay acceptable) | Supplementary source, not real-time |

## 1. Data Model Changes

### NewsEntity (modified)

```python
class NewsEntity(BaseModel):
    id: str
    canonical_title: str
    summary: str
    sources: list[str] = []
    tickers: list[str] = []
    sectors: list[str] = []
    named_entities: list[str] = []
    embedding: list[float] = []
    scope: int = 2                     # NEW: 1-5 (1=company, 5=global/geopolitical)
    score: float = 0.0
    score_factors: dict[str, float] = {}
    first_seen_at: datetime
    last_seen_at: datetime
    status: EntityStatus = EntityStatus.ACTIVE
    origin: str = "perigon"            # NEW: "perigon" | "newsapi" | "agent_fetch"
    story_cluster_size: int = 1        # NEW: article count from /stories clustering
```

**Removed:** `market: str` — news doesn't belong to a market. The `ValueEntity` retains its market field.

**Added:**
- `scope` (int, 1-5): Persisted from `_classify_scope`. Drives tiered quota enforcement.
  - 1 = single company/ticker
  - 2 = sector-level
  - 3 = industry/trend
  - 4 = national/macro (monetary policy, GDP, inflation)
  - 5 = global/geopolitical (sanctions, trade wars, OPEC, climate summits)
- `origin` (str): Tracks data source for debugging and rate limit accounting.
- `story_cluster_size` (int): From Perigon `/stories` — number of articles clustered under this story. Higher = broader coverage = likely more impactful.

## 2. Scoring Redesign

### Current formula (biased against macro news)
```
score = 0.5 * freshness + 0.3 * source_count + 0.2 * ticker_relevance
```
Macro news has zero tickers → gets 0 on 20% of the score → systematically ranked below company news.

### New formula
```
score = 0.4 * freshness + 0.25 * source_count + 0.2 * scope_factor + 0.15 * cluster_factor
```

| Factor | Calculation | Purpose |
|--------|------------|---------|
| `freshness` | `0.5 ^ (age_days / half_life_days)` | Same exponential decay (half-life 3 days) |
| `source_count` | `min(1.0, 0.2 + 0.2 * len(sources))` | More sources = higher confidence |
| `scope_factor` | `scope / 5.0` | Macro (5) → 1.0, company (1) → 0.2 |
| `cluster_factor` | `min(1.0, story_cluster_size / 20)` | 20+ articles in cluster → max score. Default 1 for non-story items → 0.05 |

**Note:** The existing `_classify_impact` and `scope_impact` fields in `perigon.py` are deprecated by this formula. The `scope` field is reused from `_classify_scope` (already implemented in `perigon.py:69-135`), and `cluster_factor` replaces impact-based ranking. The `impact` and `scope_impact` fields on pool items can be retained for backward compatibility but are no longer used in scoring.

### Worked examples

| Article | freshness | source_count | scope_factor | cluster_factor | **Old score** | **New score** |
|---------|-----------|-------------|-------------|---------------|--------------|--------------|
| "China bans rare earth exports" (1 day old, 3 sources, scope=5, cluster=25) | 0.79 | 0.80 | 1.00 | 1.00 | 0.79×50 + 0.80×30 + 0×20 = **63.5** | 0.79×40 + 0.80×25 + 1.0×20 + 1.0×15 = **86.6** |
| "AAPL beats Q2 earnings" (1 day old, 2 sources, scope=1, cluster=1, 1 ticker) | 0.79 | 0.60 | 0.20 | 0.05 | 0.79×50 + 0.60×30 + 0.30×20 = **63.5** | 0.79×40 + 0.60×25 + 0.20×20 + 0.05×15 = **51.35** |
| "Fed holds rates steady" (1 day old, 5 sources, scope=4, cluster=15) | 0.79 | 1.00 | 0.80 | 0.75 | 0.79×50 + 1.0×30 + 0×20 = **69.5** | 0.79×40 + 1.0×25 + 0.80×20 + 0.75×15 = **83.85** |

The new formula correctly prioritizes macro/geopolitical news while keeping company news visible at a lower rank.

### Tiered quota

When assembling the pool for display or session creation, enforce:

- **At least 40% of pool items must be scope >= 4** (macro/geopolitical)
- If fewer than 40% macro items exist, fill with whatever is available (no artificial inflation)
- This is a **presentation-layer filter**, not a storage filter — all news is persisted regardless

```python
def apply_tiered_quota(items: list[dict], macro_ratio: float = 0.4) -> list[dict]:
    macro = [n for n in items if n.get("scope", 0) >= 4]
    other = [n for n in items if n.get("scope", 0) < 4]

    total = len(items)
    macro_slots = int(total * macro_ratio)
    other_slots = total - min(macro_slots, len(macro))

    return macro[:macro_slots] + other[:other_slots]
```

## 3. Fetch Architecture

Three fetch modes serve different purposes in the pipeline.

### Mode 1: Cron — Perigon `/stories` (Seed Pool)

Primary source for Layer 0 seed selection. The `/stories` endpoint clusters related articles into story objects — high article count naturally surfaces breaking/impactful events.

```
Schedule: Every 2 hours
Endpoint: GET /v1/stories
Params:
  category: ["Politics", "World", "Environment", "Business", "Science"]
  excludeLabel: ["Opinion", "Non-news", "Paid News"]
  sortBy: date
  size: 20
  sourceGroup: top100
```

Each story's `articles_count` is stored as `story_cluster_size`. The story's title and summary become the `NewsEntity`.

### Mode 2: Cron — Perigon `/all` + NewsAPI `/top-headlines` (Broad Pool)

Supplements the seed pool with broader coverage for agent reference during deeper layers.

```
# Perigon /all — every 2 hours
GET /v1/all
  category: ["Politics", "World", "Environment", "Business", "Finance"]
  excludeLabel: ["Opinion", "Non-news", "Paid News"]
  sortBy: relevance
  size: 20

# NewsAPI /top-headlines — every 4 hours (budget: 100 req/day free tier)
GET /v2/top-headlines
  category: general
  language: en
  pageSize: 50
```

Both normalize to the same `NewsEntity` format. Origin tracked via `origin` field.

### Mode 3: Agent Tool — `fetch_news` (On-Demand)

The Thinker agent can actively search for news during reasoning when it identifies information gaps.

```python
class FetchNewsTool:
    """Agent tool for directed news search during causal reasoning."""
    name = "fetch_news"
    description = "Search for news articles on a specific topic to fill information gaps."

    async def run(self, query: str, max_results: int = 5) -> list[dict]:
        # Check rate limits before hitting APIs
        if not await has_api_budget():
            return await fallback_text_search(query)  # Search existing pool

        # Perigon /all first (richer metadata)
        results = await fetch_perigon_news(query=query, size=max_results)

        # Supplement with NewsAPI /everything if needed
        if len(results) < max_results:
            newsapi_results = await fetch_newsapi_everything(
                query=query, sort_by="relevancy",
                page_size=max_results - len(results)
            )
            results.extend(newsapi_results)

        # Dedup against existing pool, persist new finds
        for item in results:
            await pipeline.process_and_store(item)

        return results
```

**Rate limit protection:** Checks daily call counts before hitting APIs. If exhausted, falls back to text search against existing `news_entities` collection.

**DAG integration:** Fetched news becomes "fetch" nodes in the thinking DAG, same as today. But now they can come from live API calls, not just the pre-loaded pool.

## 4. Pipeline Changes

### Remove market partition

```python
# Before
build_news_pipeline(market="US", repo=news_repo)
build_news_pipeline(market="CN", repo=news_repo)

# After
build_news_pipeline(repo=news_repo)  # Single global pipeline
```

The `news_entities` collection becomes a single global pool. The `value_entities` collection retains its market partition.

### PoolPipeline contract changes

The current `PoolPipeline` (`pipelines/base.py`) requires `market: str` in `__init__`, passes it to `fetch.fetch(market)`, and uses it in `repo.get_all(market=market)`. These must change:

```python
# Before (base.py)
class PoolPipeline:
    def __init__(self, fetch, process, score, retain, repo, market: str): ...
    async def run(self):
        raw = await self.fetch.fetch(self.market)
        existing = await self.repo.get_all(market=self.market, ...)

# After
class PoolPipeline:
    def __init__(self, fetch, process, score, retain, repo, market: str | None = None): ...
    async def run(self):
        raw = await self.fetch.fetch() if self.market is None else await self.fetch.fetch(self.market)
        existing = await self.repo.get_all(market=self.market, ...)  # None = all markets
```

- `market` becomes `Optional[str]` with default `None`
- `BaseFetch.fetch()` interface gains an optional `market` param — news fetchers ignore it, value fetchers use it
- `NewsEntityRepo.get_all(market=None)` returns all entities (no market filter)
- `ValueEntityRepo.get_all(market="US")` still requires market — unchanged

### Dedup ID generation

The current `_gen_id` in `process.py` hashes `"{market}:{title}:{date}"`. With market removed from news:

```python
# Before
def _gen_id(self, raw: dict) -> str:
    return hashlib.sha256(f"{market}:{title}:{date}".encode()).hexdigest()[:16]

# After
def _gen_id(self, raw: dict) -> str:
    return hashlib.sha256(f"{title}:{date}".encode()).hexdigest()[:16]
```

**Migration note:** Existing entities keep their old market-prefixed IDs. New entities get market-free IDs. The hybrid similarity dedup (title + entity Jaccard) will naturally merge duplicates over time — a new market-free version of "Fed holds rates" will match the existing "US:Fed holds rates" entity by title similarity ≥ 0.6 and merge into it. No one-time migration script needed.

### Composite fetch strategy

```python
class CompositeFetch:
    """Runs multiple fetch strategies and merges results."""
    def __init__(self, fetchers: list[BaseFetch]):
        self.fetchers = fetchers

    async def fetch(self) -> list[dict]:
        results = []
        for f in self.fetchers:
            try:
                results.extend(await f.fetch())
            except Exception as e:
                log.warning("Fetcher %s failed: %s", f.__class__.__name__, e)
        return results
```

**Interface change:** `BaseFetch.fetch()` becomes a no-arg method for news fetchers. The `CompositeFetch` calls `f.fetch()` with no arguments. Value pipeline fetchers retain `fetch(market)` via the `PoolPipeline`'s market-aware path.

### Cron orchestration

```python
def build_news_pipeline(repo: NewsEntityRepo) -> PoolPipeline:
    return PoolPipeline(
        fetch=CompositeFetch([
            PerigonStoriesFetch(),    # /stories — clustered macro events
            PerigonAllFetch(),        # /all — broad coverage
            NewsAPIHeadlinesFetch(),  # /top-headlines — breaking
        ]),
        process=HybridSimilarityProcess(threshold=0.6),
        score=NewsDecayScore(),       # Updated formula with scope + cluster
        retain=ThresholdRetain(),
        repo=repo,
        market=None,                  # Global — no market partition
    )
```

## 5. NewsAPI Client

New service: `backend/src/services/newsapi.py`

```python
NEWSAPI_BASE_URL = "https://newsapi.org/v2"

async def fetch_newsapi_headlines(
    category: str = "general",
    language: str = "en",
    page_size: int = 50,
) -> list[dict]:
    """Fetch breaking headlines from /top-headlines.
    Free tier: 24h delay, 100 req/day, dev-only license.
    """

async def fetch_newsapi_everything(
    query: str,
    sort_by: str = "relevancy",
    page_size: int = 10,
) -> list[dict]:
    """Search all articles via /everything.
    Used by the agent fetch_news tool for directed search.
    """
```

Both return items normalized to pool format (same shape as Perigon items). Cached in MongoDB (`newsapi_cache` collection) with same pattern as Perigon.

### Normalization

NewsAPI items are converted to match our pool format:

```python
def _newsapi_to_pool_item(article: dict, origin: str = "newsapi") -> dict:
    return {
        "id": f"na-{hashlib.sha256(article['url'].encode()).hexdigest()[:10]}",
        "type": "news_event",
        "title": article.get("title", ""),
        "source": article.get("source", {}).get("name", "Unknown"),
        "url": article.get("url", ""),
        "summary": article.get("description", "")[:200],
        "published_at": article.get("publishedAt", ""),
        "direction": "neutral",  # NewsAPI has no sentiment
        "confidence": 50,        # Default — no sentiment data
        "sectors": _infer_sectors_from_title(article.get("title", "")),  # Keyword-based
        "scope": _infer_scope_from_title(article.get("title", "")),     # Keyword-based
        "origin": origin,
        "story_cluster_size": 1, # Not applicable for NewsAPI
    }
```

## 6. Agent Integration

### Thinker agent tool registration

The `fetch_news` tool is registered alongside existing tools in the Thinker agent's tool belt:

```python
thinker_tools = [
    FetchNewsTool(pipeline=news_pipeline),  # NEW
    # ... existing tools
]
```

**Sync/async boundary:** The current `run_thinker` in `thinking_crew.py` is a sync `def`. `FetchNewsTool.run()` is `async def` because it calls async API clients. Resolution: `FetchNewsTool` exposes a sync `_run()` wrapper that uses `asyncio.run()` or the CrewAI tool's built-in async support. Implementation should check CrewAI's tool interface — if it natively supports async tools, use that; otherwise, wrap with sync.

### Thinker reasoning flow (updated)

```
1. Receive: parent_nodes + chain_summary + news_pool (top 20, tiered)
2. Reason about causal effects from parent nodes
3. FOR EACH information gap identified:
   a. Call fetch_news("targeted query") → get relevant articles
   b. Incorporate into reasoning as additional evidence
4. Output effects with:
   - reasoning (causal chain)
   - confidence
   - parent_ids (can include freshly fetched news IDs)
   - information_gaps (remaining gaps after fetch attempts)
```

### Pool loading for sessions (updated)

```python
# Before: market-filtered
news_pool = await news_repo.find({"market": req.market, "status": "active"})

# After: global pool with tiered quota
all_active = await news_repo.find({"status": "active"}).sort("score", -1).to_list()
pool = apply_tiered_quota(all_active, macro_ratio=0.4)
```

### API contract: `StartRequest.market` retained for value pool only

```python
class StartRequest(BaseModel):
    date: str
    market: str = "US"          # KEPT — used for value pool filtering only
    max_depth: int = 3
    selected_news_ids: list[str] | None = None
```

- News pool query: `{"status": "active"}` (no market filter)
- Value pool query: `{"market": req.market, "status": "active"}` (market-filtered as before)
- Session document retains `market` field for the value pool context

### Frontend impact

No frontend changes required for the news pool. The `GET /api/pools/{date}?market=US` endpoint continues to accept `market` but applies it only to the value pool response. News items are returned globally regardless of the `market` param. The frontend's pool display component will see more diverse news without code changes.

## 7. Rate Limit Budget

| Source | Limit | Cron | Agent Tool | Hard Cap |
|--------|-------|------|------------|----------|
| Perigon | 150 calls/month (~5/day) | 3/day (stories + all) | 2/day | 5/day |
| NewsAPI (free) | 100 calls/day | 6/day (every 4h) | 44/day max | 50/day |

**Agent tool cap:** The `fetch_news` tool enforces a per-source daily cap for agent-initiated calls. When the cap is reached, it falls back to `fallback_text_search` — a MongoDB text search against the existing `news_entities` collection using `$text` index on `canonical_title` + `summary`. This ensures the agent always gets results, even when API budget is exhausted.

Centralized tracking in MongoDB:
- `perigon_usage` collection (existing) — tracks daily Perigon calls
- `newsapi_usage` collection (new) — tracks daily NewsAPI calls
- `fetch_news` tool checks both before making calls
- Each call is tagged with `source: "cron" | "agent"` for budget accounting

## 8. Migration

### Database
- `news_entities` collection: no destructive migration needed
  - New fields (`scope`, `origin`, `story_cluster_size`) default to safe values
  - `market` field can remain on existing docs (ignored, eventually cleaned up)
  - Add index on `scope` for tiered quota queries

### API
- `GET /api/pools/{date}` — remove `market` filter from news query, keep for values
- `POST /api/thinking` — update pool loading to use global news + tiered quota

### Config
- Add `NEWSAPI_API_KEY` to environment config
- Add `news_macro_quota_ratio` to `core/config.py` (default 0.4)
- Add `newsapi_daily_limit` to config (default 100)

## 9. Files Affected

| File | Change |
|------|--------|
| `backend/src/models/news_entity.py` | Add `scope`, `origin`, `story_cluster_size`; remove `market` |
| `backend/src/pipelines/base.py` | Make `market` optional in `PoolPipeline.__init__`, conditional market passing |
| `backend/src/pipelines/news/score.py` | New formula with `scope_factor` + `cluster_factor` |
| `backend/src/pipelines/news/fetch.py` | `PerigonStoriesFetch`, `PerigonAllFetch`, `NewsAPIHeadlinesFetch`, `CompositeFetch` |
| `backend/src/pipelines/news/process.py` | Remove `market` from `_gen_id` hash |
| `backend/src/services/newsapi.py` | **New** — NewsAPI client with caching + keyword-based scope/sector inference |
| `backend/src/services/perigon.py` | Add `fetch_perigon_stories()`, broaden categories |
| `backend/src/agents/tools/fetch_news.py` | **New** — agent tool for directed news search |
| `backend/src/agents/thinking_crew.py` | Register `FetchNewsTool`, handle sync/async boundary |
| `backend/src/api/pools.py` | Remove market filter on news, add tiered quota |
| `backend/src/api/thinking.py` | Update session creation — global news pool, market for values only |
| `backend/src/cron/scheduler.py` | Single news pipeline (market=None) |
| `backend/src/core/config.py` | Add `news_macro_quota_ratio`, `newsapi_daily_limit`, `newsapi_agent_cap` |
| `backend/src/database/repos/news_entity_repo.py` | Support `market=None` in `get_all()` and `get_active()` |

## 10. Open Questions

1. **Perigon `/stories` response shape** — need to verify exact fields during implementation. The design assumes `title`, `summary`, `articles_count` exist on story objects.
2. **NewsAPI free tier ToS** — "development only." If this goes to production, need paid tier (~$449/month). Acceptable for current dev/research phase.
3. **Scope classification for NewsAPI items** — NewsAPI has no pre-classified metadata. Items use `_infer_scope_from_title()` and `_infer_sectors_from_title()` — lightweight keyword-based classifiers reusing the same keyword sets from Perigon's `_classify_scope`. Accuracy will be lower than Perigon's metadata-driven classification, but sufficient for dedup and scoring. Empty sectors would cause NewsAPI items to fail Jaccard dedup against Perigon versions of the same story — keyword inference prevents this.
