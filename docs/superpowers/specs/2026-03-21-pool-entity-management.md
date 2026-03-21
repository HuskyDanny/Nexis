# Pool Entity Management

**Parent:** [Design Spec](2026-03-21-session-lifecycle-pool-entities-design.md)

## News Entity Model

```
NewsEntity
├── id                  — hash of (market + canonical_title + date) — immutable after creation
├── canonical_title     — cleaned, normalized title
├── summary
├── sources[]           — [{url, publisher, fetched_at}] — grows on merge
├── tickers[]           — extracted stock symbols
├── sectors[]           — classified sectors
├── named_entities[]    — people, orgs, events (for lexical dedup)
├── embedding           — vector for semantic similarity
├── score               — computed relevance (decays over time)
├── score_factors       — {freshness, quality, impact}
├── first_seen_at       — when first ingested
├── last_seen_at        — when last corroborated by new source
├── status              — active | stale
└── market              — US | CN
```

## Value Entity Model

```
ValueEntity
├── id                  — ticker + market
├── ticker, name, sector
├── price, pe_ratio, market_cap, cash_flow
├── price_change_pct    — daily move
├── score               — bounce-back probability
├── score_factors       — {structural_necessity, sector_position, emotional_discount,
│                          cash_flow_health, trend_alignment, macro_tailwind}
├── updated_at
├── status              — active | stale
└── market
```

## Value Scoring: Bounce-Back Probability

Not "how much did it drop" but "how likely is this to recover":

| Factor | Source | Method |
|--------|--------|--------|
| Structural necessity | Company profile + sector analysis | LLM-scored (0-1) from sector description |
| Sector position | Market cap rank within sector | Quantitative: rank / sector_size |
| Emotional discount | Price vs 52-week avg, P/E vs sector avg | Quantitative: deviation from fundamentals |
| Cash flow health | Operating cash flow from financials API | Quantitative: positive = 1, negative = 0, scaled by margin |
| Trend alignment | Sector growth rate, recent analyst consensus | LLM-scored from recent filings + news sentiment |
| Macro tailwind | Market indices, VIX, fund flow data | Quantitative: composite of market indicators |

## Cron Schedule

```
News:  Every 2 hours (captures breaking news without API abuse)
Value: Twice daily — 08:00 CST (pre-CN-open), 21:00 CST (pre-US-open)
```

## News Pipeline

```
1. FETCH     — pull from APIs (Alpha Vantage, etc.)
2. EXTRACT   — tickers, sectors, named entities from raw text
3. EMBED     — generate vector embedding
4. DEDUP     — hybrid similarity check:
               Lexical:  shared tickers + named entities + date overlap
               Semantic: cosine similarity on embeddings
               Combined: 0.4 * lexical + 0.6 * semantic
               Above threshold → MERGE (add source, update last_seen_at)
               Below threshold → INSERT as new entity
5. SCORE     — freshness (decay) + quality (source count) + impact (sector breadth)
6. PERSIST   — upsert to MongoDB news_entities collection
7. FILTER    — score < threshold → status = stale
```

## Value Pipeline

```
1. FETCH     — pull fundamentals (Yahoo Finance, etc.)
2. UPSERT    — by ticker+market (ticker is identity, no dedup)
3. SCORE     — bounce-back probability (multi-factor model)
4. PERSIST   — upsert to MongoDB value_entities collection
5. FILTER    — score < threshold → status = stale
```

## News Decay Function

```python
def news_decay(first_seen_at: datetime, impact: float, quality: float) -> float:
    age_hours = (now - first_seen_at).total_seconds() / 3600
    half_life = 24 * (1 + impact * 2 + quality * 1)
    # Fed rate decision: ~86 hours half-life
    # Minor earnings beat: ~41 hours half-life
    return 100 * (0.5 ** (age_hours / half_life))
```

Merge resets freshness boost — corroborated stories stay relevant longer.

Safety net: auto-stale after 7 days regardless of score (configurable `news_max_age_days`).

## Error Handling (Cron Pipelines)

- Pipeline failures logged and recorded in `pipeline_runs` collection (existing `PipelineRun` model).
- **Partial failures** — if fetch returns 80 items but 5 fail processing, the 75 successful items are still persisted. Failures logged individually.
- **Total failures** (API down, rate limited) — recorded as failed run with error message. Previous entities remain untouched.
- **Consecutive failures** — if 3+ runs fail in a row, set a `pipeline_status: degraded` flag in config. Alerts can subscribe to this.

## API Changes

```
GET /api/pools/{date}?market=US                     → active entities only (default)
GET /api/pools/{date}?market=US&include_stale=true   → all entities including stale
```

## MongoDB Collections

| Collection | Replaces | Purpose |
|---|---|---|
| `news_entities` | `pools` (type=news) | Owned news entities with embeddings, scores |
| `value_entities` | `pools` (type=value) | Owned value entities with bounce-back scores |
