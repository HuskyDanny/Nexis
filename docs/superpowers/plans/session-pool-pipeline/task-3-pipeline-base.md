### Task 3: Pipeline Base (Orchestrator + ThresholdRetain)

**Parent:** [Session & Pool Pipeline Plan](../2026-03-22-session-pool-entity-pipeline.md)

**Files:**
- Create: `backend/src/pipelines/__init__.py`, `backend/src/pipelines/base.py`
- Test: `backend/tests/test_pipeline_base.py`

**Dependencies:** Task 2 (pool_common.py)

---

- [ ] **Step 1: Write failing tests — `backend/tests/test_pipeline_base.py`**

```python
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.pipelines.base import PoolPipeline, ThresholdRetain
from src.models.pool_common import ProcessResult, ScoreResult

@pytest.fixture
def mock_fetch():
    s = AsyncMock()
    s.fetch.return_value = [{"title": "New headline", "source": "https://ex.com"}]
    return s

@pytest.fixture
def mock_process():
    s = AsyncMock()
    s.process.return_value = ProcessResult(action="insert", entity_id="hash_new")
    return s

@pytest.fixture
def mock_score():
    s = MagicMock()
    s.score.return_value = ScoreResult(score=0.8, factors={"freshness": 0.9})
    return s

@pytest.fixture
def mock_retain():
    s = MagicMock()
    s.should_retain.return_value = True
    return s

@pytest.fixture
def mock_repo():
    r = AsyncMock()
    r.get_all.return_value = []
    return r

@pytest.fixture
def pipeline(mock_fetch, mock_process, mock_score, mock_retain, mock_repo):
    return PoolPipeline(
        fetch=mock_fetch, process=mock_process, score=mock_score,
        retain=mock_retain, repo=mock_repo, market="US",
    )

async def test_inserts_new_entity(pipeline, mock_repo):
    result = await pipeline.run()
    assert result.inserted == 1 and result.merged == 0
    assert mock_repo.upsert.await_count >= 1

async def test_merges_existing(pipeline, mock_repo, mock_process):
    mock_process.process.return_value = ProcessResult(
        action="merge", entity_id="h_old", merged_from="h_raw"
    )
    result = await pipeline.run()
    assert result.merged == 1 and result.inserted == 0

async def test_rescores_existing(mock_fetch, mock_process, mock_score, mock_retain, mock_repo):
    now = datetime.now(timezone.utc).isoformat()
    mock_repo.get_all.return_value = [
        {"id": "e1", "status": "active", "score": 0.9, "score_factors": {}, "last_seen_at": now},
        {"id": "e2", "status": "active", "score": 0.5, "score_factors": {},
         "last_seen_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()},
    ]
    mock_fetch.fetch.return_value = []
    mock_score.score.return_value = ScoreResult(score=0.4, factors={"freshness": 0.4})
    mock_retain.should_retain.side_effect = [True, False]
    p = PoolPipeline(fetch=mock_fetch, process=mock_process, score=mock_score,
                     retain=mock_retain, repo=mock_repo, market="US")
    result = await p.run()
    assert result.rescored == 2 and result.removed == 1

async def test_stales_below_threshold(mock_fetch, mock_process, mock_score, mock_retain, mock_repo):
    mock_repo.get_all.return_value = [{
        "id": "s1", "status": "active", "score": 0.1, "score_factors": {},
        "last_seen_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
    }]
    mock_fetch.fetch.return_value = []
    mock_score.score.return_value = ScoreResult(score=0.05, factors={"freshness": 0.05})
    mock_retain.should_retain.return_value = False
    p = PoolPipeline(fetch=mock_fetch, process=mock_process, score=mock_score,
                     retain=mock_retain, repo=mock_repo, market="US")
    result = await p.run()
    assert result.removed == 1
    stale = [c for c in mock_repo.upsert.call_args_list if c[0][0].get("status") == "stale"]
    assert len(stale) == 1

# --- ThresholdRetain ---
def test_keeps_above_min():
    r = ThresholdRetain(min_score=0.3)
    assert r.should_retain({"score": 0.5, "last_seen_at": datetime.now(timezone.utc).isoformat()})

def test_removes_below_min():
    r = ThresholdRetain(min_score=0.3)
    assert not r.should_retain({"score": 0.1, "last_seen_at": datetime.now(timezone.utc).isoformat()})

def test_removes_old():
    r = ThresholdRetain(min_score=0.1, max_age_days=7)
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    assert not r.should_retain({"score": 0.5, "last_seen_at": old})

def test_keeps_recent():
    r = ThresholdRetain(min_score=0.1, max_age_days=7)
    assert r.should_retain({"score": 0.5, "last_seen_at": datetime.now(timezone.utc).isoformat()})

def test_no_max_age_keeps_old():
    r = ThresholdRetain(min_score=0.1)
    old = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    assert r.should_retain({"score": 0.5, "last_seen_at": old})
```

Run: `cd backend && python -m pytest tests/test_pipeline_base.py -v` — expect FAIL.

- [ ] **Step 2: Implement — `backend/src/pipelines/base.py`**

Create empty `backend/src/pipelines/__init__.py`.

```python
from datetime import datetime, timezone, timedelta
from src.models.pool_common import PipelineResult, ScoreResult

class ThresholdRetain:
    def __init__(self, min_score: float, max_age_days: int | None = None):
        self.min_score = min_score
        self.max_age_days = max_age_days

    def should_retain(self, entity: dict) -> bool:
        if entity.get("score", 0) < self.min_score:
            return False
        if self.max_age_days is not None:
            last_seen = entity.get("last_seen_at", "")
            dt = datetime.fromisoformat(last_seen) if isinstance(last_seen, str) else last_seen
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - dt) > timedelta(days=self.max_age_days):
                return False
        return True

class PoolPipeline:
    def __init__(self, fetch, process, score, retain, repo, market: str):
        self.fetch = fetch
        self.process = process
        self.score = score
        self.retain = retain
        self.repo = repo
        self.market = market

    async def run(self) -> PipelineResult:
        result = PipelineResult()
        raw_items = await self.fetch.fetch(self.market)
        existing = await self.repo.get_all(market=self.market, include_stale=True)

        touched: set[str] = set()
        for raw in raw_items:
            pr = await self.process.process(raw, existing)
            sr: ScoreResult = self.score.score(raw)
            entity = {**raw, "id": pr.entity_id, "score": sr.score,
                      "score_factors": sr.factors, "status": "active"}
            await self.repo.upsert(entity)
            touched.add(pr.entity_id)
            if pr.action == "insert":
                result.inserted += 1
            else:
                result.merged += 1

        for entity in existing:
            eid = entity.get("id", "")
            if eid in touched:
                continue
            sr = self.score.score(entity)
            entity["score"] = sr.score
            entity["score_factors"] = sr.factors
            result.rescored += 1
            if not self.retain.should_retain(entity):
                entity["status"] = "stale"
                result.removed += 1
            await self.repo.upsert(entity)

        return result
```

Run: `cd backend && python -m pytest tests/test_pipeline_base.py -v` — expect PASS.

- [ ] **Step 3: Commit**

Commit: `feat(pipeline-base): add PoolPipeline orchestrator + ThresholdRetain strategy`
