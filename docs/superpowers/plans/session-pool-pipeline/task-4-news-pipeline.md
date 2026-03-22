### Task 4: News Pipeline Strategies

**Parent:** [Session & Pool Pipeline Plan](../2026-03-22-session-pool-entity-pipeline.md)

**Files:**
- Create: `backend/src/pipelines/news/__init__.py`
- Create: `backend/src/pipelines/news/score.py`, `backend/src/pipelines/news/process.py`, `backend/src/pipelines/news/fetch.py`
- Test: `backend/tests/test_news_pipeline.py`

**Dependencies:** Task 2 (entity models), Task 3 (pipeline base)

---

- [ ] **Step 1: Write failing tests — `backend/tests/test_news_pipeline.py`**

```python
from datetime import datetime, timezone, timedelta
import pytest
from src.pipelines.news.score import NewsDecayScore
from src.pipelines.news.process import HybridSimilarityProcess
from src.pipelines.news.fetch import AlphaVantageNewsFetch

# --- NewsDecayScore ---
def _entity(age_days=0, sources=1, tickers=1):
    dt = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    return {"first_seen_at": dt, "last_seen_at": dt,
            "sources": [f"s{i}" for i in range(sources)],
            "tickers": [f"T{i}" for i in range(tickers)]}

def test_fresh_news_high_score():
    r = NewsDecayScore(half_life_days=3.0).score(_entity(age_days=0))
    assert r.score >= 0.8 and r.factors["freshness"] >= 0.9

def test_old_news_low_score():
    r = NewsDecayScore(half_life_days=3.0).score(_entity(age_days=10))
    assert r.score < 0.3 and r.factors["freshness"] < 0.15

def test_half_life_freshness():
    r = NewsDecayScore(half_life_days=3.0).score(_entity(age_days=3))
    assert 0.4 < r.factors["freshness"] < 0.6

def test_multi_source_boost():
    r = NewsDecayScore(half_life_days=3.0).score(_entity(sources=3, tickers=2))
    assert r.factors["source_count"] > 0.5

def test_no_tickers():
    r = NewsDecayScore(half_life_days=3.0).score(_entity(tickers=0))
    assert r.factors.get("ticker_relevance", 0) == 0.0

# --- HybridSimilarityProcess ---
async def test_insert_no_existing():
    p = HybridSimilarityProcess(title_threshold=0.6, entity_threshold=0.5)
    r = await p.process(
        {"title": "Fed holds rates", "tickers": ["SPY"], "named_entities": ["Fed"]},
        existing=[],
    )
    assert r.action == "insert" and r.entity_id != "" and r.merged_from is None

async def test_insert_no_similar():
    p = HybridSimilarityProcess(title_threshold=0.6, entity_threshold=0.5)
    r = await p.process(
        {"title": "Oil surge OPEC cuts", "tickers": ["USO"], "named_entities": ["OPEC"]},
        existing=[{"id": "e1", "canonical_title": "Fed holds rates",
                   "tickers": ["SPY"], "named_entities": ["Fed"]}],
    )
    assert r.action == "insert"

async def test_merge_similar_title():
    p = HybridSimilarityProcess(title_threshold=0.5, entity_threshold=0.5)
    r = await p.process(
        {"title": "Federal Reserve holds interest rates steady",
         "tickers": ["SPY"], "named_entities": ["Federal Reserve"]},
        existing=[{"id": "e_fed", "canonical_title": "Fed holds rates steady for March meeting",
                   "tickers": ["SPY"], "named_entities": ["Federal Reserve"]}],
    )
    assert r.action == "merge" and r.entity_id == "e_fed"

async def test_merge_shared_entities():
    p = HybridSimilarityProcess(title_threshold=0.8, entity_threshold=0.4)
    r = await p.process(
        {"title": "Completely different headline about rates",
         "tickers": ["SPY", "TLT"], "named_entities": ["Federal Reserve", "Jerome Powell"]},
        existing=[{"id": "e_fed", "canonical_title": "Fed signals rate pause",
                   "tickers": ["SPY"], "named_entities": ["Federal Reserve", "Jerome Powell"]}],
    )
    assert r.action == "merge" and r.entity_id == "e_fed"

# --- AlphaVantageNewsFetch ---
async def test_fetch_placeholder_empty():
    r = await AlphaVantageNewsFetch().fetch(market="US")
    assert isinstance(r, list) and len(r) == 0
```

Run: `cd backend && python -m pytest tests/test_news_pipeline.py -v` — expect FAIL.

- [ ] **Step 2: Implement NewsDecayScore — `backend/src/pipelines/news/score.py`**

Create empty `backend/src/pipelines/news/__init__.py`.

```python
import math
from datetime import datetime, timezone
from src.models.pool_common import ScoreResult

class NewsDecayScore:
    def __init__(self, half_life_days: float = 3.0):
        self.half_life_days = half_life_days

    def score(self, entity: dict) -> ScoreResult:
        freshness = self._freshness(entity)
        source_count = self._source_factor(entity)
        ticker_relevance = self._ticker_factor(entity)
        score = 0.5 * freshness + 0.3 * source_count + 0.2 * ticker_relevance
        return ScoreResult(score=round(score, 4), factors={
            "freshness": round(freshness, 4),
            "source_count": round(source_count, 4),
            "ticker_relevance": round(ticker_relevance, 4),
        })

    def _freshness(self, entity: dict) -> float:
        last_seen = entity.get("last_seen_at", "")
        if not last_seen:
            return 0.0
        dt = datetime.fromisoformat(last_seen) if isinstance(last_seen, str) else last_seen
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
        return math.pow(0.5, age_days / self.half_life_days)

    def _source_factor(self, entity: dict) -> float:
        count = len(entity.get("sources", []))
        return min(1.0, 0.2 + 0.2 * count) if count else 0.0

    def _ticker_factor(self, entity: dict) -> float:
        count = len(entity.get("tickers", []))
        return min(1.0, 0.3 * count) if count else 0.0
```

Run: `cd backend && python -m pytest tests/test_news_pipeline.py -k score -v` — expect PASS.

- [ ] **Step 3: Implement HybridSimilarityProcess — `backend/src/pipelines/news/process.py`**

```python
import hashlib
from datetime import datetime, timezone
from src.models.pool_common import ProcessResult

class HybridSimilarityProcess:
    def __init__(self, title_threshold: float = 0.6, entity_threshold: float = 0.5):
        self.title_threshold = title_threshold
        self.entity_threshold = entity_threshold

    async def process(self, raw: dict, existing: list[dict]) -> ProcessResult:
        raw_tokens = self._tokenize(raw.get("title", ""))
        raw_tickers = set(raw.get("tickers", []))
        raw_ents = set(raw.get("named_entities", []))
        best_id, best_score = None, 0.0

        for e in existing:
            title_sim = self._jaccard(raw_tokens, self._tokenize(e.get("canonical_title", "")))
            ticker_sim = self._jaccard(raw_tickers, set(e.get("tickers", [])))
            ent_sim = self._jaccard(raw_ents, set(e.get("named_entities", [])))
            combined = 0.4 * title_sim + 0.3 * ticker_sim + 0.3 * ent_sim
            if combined > best_score:
                best_score, best_id = combined, e.get("id")

        if best_id and (best_score >= self.title_threshold or best_score >= self.entity_threshold):
            return ProcessResult(action="merge", entity_id=best_id,
                                 merged_from=self._gen_id(raw))
        return ProcessResult(action="insert", entity_id=self._gen_id(raw))

    def _tokenize(self, text: str) -> set[str]:
        return set(text.lower().split())

    def _jaccard(self, a: set, b: set) -> float:
        if not a and not b:
            return 0.0
        union = a | b
        return len(a & b) / len(union) if union else 0.0

    def _gen_id(self, raw: dict) -> str:
        title = raw.get("title", "")
        market = raw.get("market", "US")
        date = raw.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        return hashlib.sha256(f"{market}:{title}:{date}".encode()).hexdigest()[:16]
```

Run: `cd backend && python -m pytest tests/test_news_pipeline.py -k process -v` — expect PASS.

- [ ] **Step 4: Implement AlphaVantageNewsFetch — `backend/src/pipelines/news/fetch.py`**

```python
class AlphaVantageNewsFetch:
    """Placeholder — returns empty until API key is configured."""

    async def fetch(self, market: str) -> list[dict]:
        return []
```

Run: `cd backend && python -m pytest tests/test_news_pipeline.py -v` — expect all PASS.

- [ ] **Step 5: Commit**

Commit: `feat(news-pipeline): add NewsDecayScore, HybridSimilarityProcess, and fetch placeholder`
