### Task 2: Entity Models + Repositories

**Parent:** [Session & Pool Pipeline Plan](../2026-03-22-session-pool-entity-pipeline.md)

**Files:**
- Create: `backend/src/models/news_entity.py`, `backend/src/models/value_entity.py`, `backend/src/models/pool_common.py`
- Create: `backend/src/database/repositories/news_entity_repo.py`, `backend/src/database/repositories/value_entity_repo.py`
- Test: `backend/tests/test_entity_models.py`, `backend/tests/test_entity_repos.py`

---

- [ ] **Step 1: Write failing model tests — `backend/tests/test_entity_models.py`**

```python
from src.models.news_entity import NewsEntity, EntityStatus
from src.models.value_entity import ValueEntity
from src.models.pool_common import ScoreResult, ProcessResult, PipelineResult

def test_news_entity_defaults():
    e = NewsEntity(id="h1", canonical_title="Fed rates", summary="S", sources=["x"], market="US")
    assert e.score == 0.0 and e.embedding == [] and e.status == EntityStatus.ACTIVE
    assert e.tickers == [] and e.sectors == [] and e.named_entities == []
    assert e.first_seen_at is not None and e.last_seen_at is not None

def test_news_entity_with_score():
    e = NewsEntity(id="h2", canonical_title="Oil", summary="S", sources=["x"],
                   market="US", score=0.85, score_factors={"f": 0.9}, embedding=[0.1, 0.2])
    assert e.score == 0.85 and e.embedding == [0.1, 0.2]

def test_entity_status_values():
    assert EntityStatus.ACTIVE == "active"
    assert EntityStatus.STALE == "stale"
    assert EntityStatus.ARCHIVED == "archived"

def test_value_entity_defaults():
    e = ValueEntity(id="AAPL:US", ticker="AAPL", name="Apple", sector="Tech", market="US")
    assert e.price is None and e.pe_ratio is None and e.score == 0.0
    assert e.status == EntityStatus.ACTIVE and e.updated_at is not None

def test_value_entity_with_fundamentals():
    e = ValueEntity(id="MSFT:US", ticker="MSFT", name="Microsoft", sector="Tech",
                    market="US", price=420.5, pe_ratio=35.2, market_cap=3.1e12,
                    cash_flow=8.7e10, price_change_pct=-2.1, score=0.72)
    assert e.price == 420.5 and e.pe_ratio == 35.2 and e.score == 0.72

def test_score_result():
    sr = ScoreResult(score=0.75, factors={"freshness": 0.8})
    assert sr.score == 0.75

def test_process_result_insert():
    pr = ProcessResult(action="insert", entity_id="h1")
    assert pr.merged_from is None

def test_process_result_merge():
    pr = ProcessResult(action="merge", entity_id="h1", merged_from="h0")
    assert pr.merged_from == "h0"

def test_pipeline_result():
    r = PipelineResult(inserted=3, merged=1, rescored=10, removed=2)
    assert r.inserted == 3 and r.removed == 2
```

Run: `cd backend && python -m pytest tests/test_entity_models.py -v` — expect FAIL.

- [ ] **Step 2: Implement models**

`backend/src/models/pool_common.py`:
```python
from typing import Protocol, runtime_checkable
from pydantic import BaseModel

class ScoreResult(BaseModel):
    score: float
    factors: dict[str, float]

class ProcessResult(BaseModel):
    action: str  # "insert" or "merge"
    entity_id: str
    merged_from: str | None = None

class PipelineResult(BaseModel):
    inserted: int = 0
    merged: int = 0
    rescored: int = 0
    removed: int = 0

@runtime_checkable
class FetchStrategy(Protocol):
    async def fetch(self, market: str) -> list[dict]: ...

@runtime_checkable
class ProcessStrategy(Protocol):
    async def process(self, raw: dict, existing: list[dict]) -> ProcessResult: ...

@runtime_checkable
class ScoreStrategy(Protocol):
    def score(self, entity: dict) -> ScoreResult: ...

@runtime_checkable
class RetainStrategy(Protocol):
    def should_retain(self, entity: dict) -> bool: ...
```

`backend/src/models/news_entity.py`:
```python
from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, Field

class EntityStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"

class NewsEntity(BaseModel):
    id: str
    canonical_title: str
    summary: str
    sources: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    named_entities: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)
    score: float = 0.0
    score_factors: dict[str, float] = Field(default_factory=dict)
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: EntityStatus = EntityStatus.ACTIVE
    market: str = "US"
```

`backend/src/models/value_entity.py`:
```python
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from src.models.news_entity import EntityStatus

class ValueEntity(BaseModel):
    id: str
    ticker: str
    name: str
    sector: str
    price: float | None = None
    pe_ratio: float | None = None
    market_cap: float | None = None
    cash_flow: float | None = None
    price_change_pct: float | None = None
    score: float = 0.0
    score_factors: dict[str, float] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: EntityStatus = EntityStatus.ACTIVE
    market: str = "US"
```

Run: `cd backend && python -m pytest tests/test_entity_models.py -v` — expect PASS.

- [ ] **Step 3: Write failing repo tests — `backend/tests/test_entity_repos.py`**

```python
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.database.repositories.news_entity_repo import NewsEntityRepo
from src.database.repositories.value_entity_repo import ValueEntityRepo

@pytest.fixture
def col():
    return AsyncMock()

# --- NewsEntityRepo ---
@pytest.fixture
def news_repo(col):
    return NewsEntityRepo(col)

async def test_news_upsert(news_repo, col):
    entity = {"id": "h1", "canonical_title": "Fed", "status": "active"}
    await news_repo.upsert(entity)
    col.replace_one.assert_awaited_once_with({"id": "h1"}, entity, upsert=True)

async def test_news_get_by_id(news_repo, col):
    col.find_one.return_value = {"id": "h1"}
    assert await news_repo.get_by_id("h1") == {"id": "h1"}
    col.find_one.assert_awaited_once_with({"id": "h1"}, {"_id": 0})

async def test_news_get_by_id_none(news_repo, col):
    col.find_one.return_value = None
    assert await news_repo.get_by_id("x") is None

async def test_news_get_active(news_repo, col):
    cursor = AsyncMock()
    cursor.to_list.return_value = [{"id": "a"}]
    col.find.return_value = cursor
    result = await news_repo.get_active(market="US")
    assert result == [{"id": "a"}]
    col.find.assert_called_once_with({"status": "active", "market": "US"}, {"_id": 0})

async def test_news_get_all_with_stale(news_repo, col):
    cursor = AsyncMock()
    cursor.to_list.return_value = [{"id": "a"}, {"id": "b"}]
    col.find.return_value = cursor
    result = await news_repo.get_all(market="US", include_stale=True)
    assert len(result) == 2
    col.find.assert_called_once_with(
        {"status": {"$in": ["active", "stale"]}, "market": "US"}, {"_id": 0}
    )

# --- ValueEntityRepo ---
@pytest.fixture
def val_col():
    return AsyncMock()

@pytest.fixture
def val_repo(val_col):
    return ValueEntityRepo(val_col)

async def test_value_upsert(val_repo, val_col):
    entity = {"id": "AAPL:US", "ticker": "AAPL"}
    await val_repo.upsert(entity)
    val_col.replace_one.assert_awaited_once_with({"id": "AAPL:US"}, entity, upsert=True)

async def test_value_get_by_id(val_repo, val_col):
    val_col.find_one.return_value = {"id": "AAPL:US"}
    assert await val_repo.get_by_id("AAPL:US") == {"id": "AAPL:US"}

async def test_value_get_active(val_repo, val_col):
    cursor = AsyncMock()
    cursor.to_list.return_value = [{"id": "AAPL:US"}]
    val_col.find.return_value = cursor
    assert await val_repo.get_active(market="US") == [{"id": "AAPL:US"}]
```

Run: `cd backend && python -m pytest tests/test_entity_repos.py -v` — expect FAIL.

- [ ] **Step 4: Implement repos**

Both repos share the same pattern. `backend/src/database/repositories/news_entity_repo.py`:
```python
from motor.motor_asyncio import AsyncIOMotorCollection

class NewsEntityRepo:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def upsert(self, entity: dict) -> None:
        await self.collection.replace_one({"id": entity["id"]}, entity, upsert=True)

    async def get_by_id(self, entity_id: str) -> dict | None:
        return await self.collection.find_one({"id": entity_id}, {"_id": 0})

    async def get_active(self, market: str) -> list[dict]:
        cursor = self.collection.find({"status": "active", "market": market}, {"_id": 0})
        return await cursor.to_list(length=None)

    async def get_all(self, market: str, include_stale: bool = False) -> list[dict]:
        q = {"status": {"$in": ["active", "stale"]}, "market": market} if include_stale \
            else {"status": "active", "market": market}
        return await self.collection.find(q, {"_id": 0}).to_list(length=None)
```

`backend/src/database/repositories/value_entity_repo.py` — identical structure, same class name `ValueEntityRepo`.

Run: `cd backend && python -m pytest tests/test_entity_repos.py tests/test_entity_models.py -v` — expect PASS.

- [ ] **Step 5: Commit**

Commit: `feat(entity-models): add NewsEntity, ValueEntity, pool_common, and repos`
