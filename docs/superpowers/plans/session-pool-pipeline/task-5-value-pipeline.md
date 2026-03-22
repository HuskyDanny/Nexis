### Task 5: Value Pipeline Strategies

**Parent:** [Session & Pool Pipeline Plan](../2026-03-22-session-pool-entity-pipeline.md)

**Files:**
- Create: `backend/src/pipelines/value/fetch.py`, `backend/src/pipelines/value/process.py`, `backend/src/pipelines/value/score.py`
- Create: `backend/tests/pipelines/value/test_fetch.py`, `backend/tests/pipelines/value/test_process.py`, `backend/tests/pipelines/value/test_score.py`
- Depends on: Task 2 (ValueEntity model, ValueEntityRepo), Task 3 (PoolPipeline base, ScoreResult, ProcessResult)

---

- [ ] **Step 1: RED — BounceBackScore tests**

Create `backend/tests/pipelines/value/test_score.py`:

```python
import pytest
from src.pipelines.value.score import BounceBackScore

class TestBounceBackScore:
    def setup_method(self):
        self.scorer = BounceBackScore()

    def test_high_opportunity_big_drop_good_fundamentals(self):
        entity = {"ticker": "AAPL", "price_change_pct": -15.0, "cash_flow": 5e9, "market_cap": 2e11}
        result = self.scorer.score(entity)
        assert result.total > 50, f"Expected >50, got {result.total}"

    def test_low_opportunity_stable_expensive(self):
        entity = {"ticker": "TINY", "price_change_pct": 2.0, "cash_flow": -1e8, "market_cap": 5e8}
        result = self.scorer.score(entity)
        assert result.total < 30, f"Expected <30, got {result.total}"

    def test_emotional_discount_caps_at_one(self):
        entity = {"ticker": "CRASH", "price_change_pct": -50.0, "cash_flow": 1e9, "market_cap": 1e10}
        assert self.scorer.score(entity).factors["emotional_discount"] == 1.0

    def test_positive_price_gives_zero_discount(self):
        entity = {"ticker": "UP", "price_change_pct": 10.0, "cash_flow": 1e9, "market_cap": 1e10}
        assert self.scorer.score(entity).factors["emotional_discount"] == 0.0

    def test_negative_cash_flow_gives_zero_health(self):
        entity = {"ticker": "BURN", "price_change_pct": -10.0, "cash_flow": -5e9, "market_cap": 1e10}
        assert self.scorer.score(entity).factors["cash_flow_health"] == 0.0

    def test_score_has_all_six_factors(self):
        entity = {"ticker": "T", "price_change_pct": -5.0, "cash_flow": 1e9, "market_cap": 5e10}
        expected = {"structural_necessity", "sector_position", "emotional_discount",
                    "cash_flow_health", "trend_alignment", "macro_tailwind"}
        assert set(self.scorer.score(entity).factors.keys()) == expected
```

Run: `cd backend && python -m pytest tests/pipelines/value/test_score.py -v`
Expected: 6 FAIL (`ModuleNotFoundError`)

- [ ] **Step 2: GREEN — Implement BounceBackScore**

Create `backend/src/pipelines/value/__init__.py` (empty).

Create `backend/src/pipelines/value/score.py`:

```python
"""Value scoring — bounce-back probability model."""
from src.pipelines.base import ScoreResult

WEIGHTS = {
    "structural_necessity": 0.20, "sector_position": 0.15,
    "emotional_discount": 0.20, "cash_flow_health": 0.20,
    "trend_alignment": 0.15, "macro_tailwind": 0.10,
}

class BounceBackScore:
    """Multi-factor bounce-back probability scorer.
    Quantitative factors from entity data; LLM-scored factors use 0.5 placeholder."""

    def score(self, entity: dict) -> ScoreResult:
        price_change = entity.get("price_change_pct", 0.0)
        cash_flow = entity.get("cash_flow", 0.0)
        market_cap = entity.get("market_cap", 0.0)

        factors = {
            "structural_necessity": 0.5,  # LLM placeholder
            "sector_position": round(min(market_cap / 1e11, 1.0), 4),
            "emotional_discount": round(min(abs(min(price_change, 0.0)) / 20.0, 1.0), 4),
            "cash_flow_health": round(min(max(0.0, cash_flow) / 1e10, 1.0), 4),
            "trend_alignment": 0.5,  # LLM placeholder
            "macro_tailwind": 0.5,  # LLM placeholder
        }
        total = round(sum(factors[k] * WEIGHTS[k] for k in WEIGHTS) * 100, 1)
        return ScoreResult(total=total, factors=factors)
```

Run: `cd backend && python -m pytest tests/pipelines/value/test_score.py -v` — 6 PASS

- [ ] **Step 3: RED — TickerUpsertProcess tests**

Create `backend/tests/pipelines/value/test_process.py`:

```python
import pytest
from src.pipelines.value.process import TickerUpsertProcess

class TestTickerUpsertProcess:
    def setup_method(self):
        self.proc = TickerUpsertProcess()

    @pytest.mark.asyncio
    async def test_insert_new_ticker(self):
        result = await self.proc.process(
            {"ticker": "AAPL", "market": "US", "price": 150.0, "name": "Apple"}, [])
        assert result.action == "insert"
        assert result.new_entity["id"] == "AAPL:US"
        assert result.merged_entity is None

    @pytest.mark.asyncio
    async def test_merge_existing_ticker(self):
        existing = [{"id": "AAPL:US", "ticker": "AAPL", "market": "US",
                     "price": 150.0, "pe_ratio": 27.0, "name": "Apple Inc"}]
        result = await self.proc.process(
            {"ticker": "AAPL", "market": "US", "price": 155.0, "pe_ratio": 28.5}, existing)
        assert result.action == "merge"
        assert result.merged_entity["price"] == 155.0
        assert result.merged_entity["name"] == "Apple Inc"

    @pytest.mark.asyncio
    async def test_entity_id_format(self):
        result = await self.proc.process({"ticker": "BABA", "market": "CN", "price": 80.0}, [])
        assert result.new_entity["id"] == "BABA:CN"

    @pytest.mark.asyncio
    async def test_merge_preserves_unset_fields(self):
        existing = [{"id": "MSFT:US", "ticker": "MSFT", "market": "US",
                     "price": 390.0, "sector": "Technology", "cash_flow": 6e9}]
        result = await self.proc.process({"ticker": "MSFT", "market": "US", "price": 400.0}, existing)
        assert result.merged_entity["sector"] == "Technology"
        assert result.merged_entity["cash_flow"] == 6e9
```

Run: `cd backend && python -m pytest tests/pipelines/value/test_process.py -v` — 4 FAIL

- [ ] **Step 4: GREEN — Implement TickerUpsertProcess**

Create `backend/src/pipelines/value/process.py`:

```python
"""Value processing — ticker-based upsert."""
from datetime import datetime, timezone
from src.pipelines.base import ProcessResult

class TickerUpsertProcess:
    """Upsert by ticker:market. Merge updates fields; insert creates new entity."""

    async def process(self, raw: dict, existing: list[dict]) -> ProcessResult:
        ticker = raw.get("ticker", "")
        market = raw.get("market", "US")
        entity_id = f"{ticker}:{market}"
        match = next((e for e in existing if e.get("id") == entity_id), None)
        now = datetime.now(timezone.utc).isoformat()

        if match:
            merged = {**match}
            for k, v in raw.items():
                if v is not None:
                    merged[k] = v
            merged["id"] = entity_id
            merged["updated_at"] = now
            return ProcessResult(action="merge", merged_entity=merged, new_entity=None)

        new_entity = {"id": entity_id, "ticker": ticker, "market": market,
                      "status": "active", "updated_at": now}
        for k, v in raw.items():
            if k != "id" and v is not None:
                new_entity[k] = v
        return ProcessResult(action="insert", new_entity=new_entity, merged_entity=None)
```

Run: `cd backend && python -m pytest tests/pipelines/value/test_process.py -v` — 4 PASS

- [ ] **Step 5: RED+GREEN — YahooFinanceFetch (placeholder)**

Create `backend/tests/pipelines/value/test_fetch.py`:

```python
import pytest
from src.pipelines.value.fetch import YahooFinanceFetch

class TestYahooFinanceFetch:
    @pytest.mark.asyncio
    async def test_fetch_returns_list(self):
        assert isinstance(await YahooFinanceFetch().fetch("US"), list)

    @pytest.mark.asyncio
    async def test_fetch_returns_empty(self):
        assert len(await YahooFinanceFetch().fetch("CN")) == 0
```

Create `backend/src/pipelines/value/fetch.py`:

```python
"""Value fetching — Yahoo Finance placeholder."""
from src.core.logger import get_logger

log = get_logger("pipelines.value.fetch")

class YahooFinanceFetch:
    """Placeholder. Returns empty list until API key available."""

    async def fetch(self, market: str) -> list[dict]:
        log.info("YahooFinanceFetch.fetch(market=%s) — placeholder", market)
        return []
```

Run: `cd backend && python -m pytest tests/pipelines/value/ -v` — all 12 PASS
