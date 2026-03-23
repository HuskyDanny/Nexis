### Task 3: Iran Escalation Scenario

**Files:**
- Create: `backend/tests/benchmark/scenarios/__init__.py`
- Create: `backend/tests/benchmark/scenarios/iran_escalation.py`
- Test: `backend/tests/benchmark/test_scenario.py`

- [ ] **Step 1: Write failing test for scenario validation**

```python
# backend/tests/benchmark/test_scenario.py
import pytest
from tests.benchmark.scenarios.iran_escalation import SCENARIO


class TestIranEscalationScenario:
    def test_has_required_fields(self):
        required = ["id", "name", "description", "news_pool", "value_pool",
                     "expected_depth", "checkpoints", "expected_matches", "expected_skills"]
        for field in required:
            assert field in SCENARIO, f"Missing: {field}"

    def test_news_pool_has_items(self):
        assert len(SCENARIO["news_pool"]) >= 3
        for item in SCENARIO["news_pool"]:
            assert "title" in item and "summary" in item

    def test_value_pool_has_items(self):
        assert len(SCENARIO["value_pool"]) >= 3
        for item in SCENARIO["value_pool"]:
            assert "ticker" in item and "name" in item and "sector" in item

    def test_checkpoints_cover_all_layers(self):
        for layer in range(1, SCENARIO["expected_depth"] + 1):
            assert layer in SCENARIO["checkpoints"]
            required_count = sum(1 for cp in SCENARIO["checkpoints"][layer] if cp["required"])
            assert required_count >= 1

    def test_expected_matches_have_direction(self):
        for match in SCENARIO["expected_matches"]:
            assert match["direction"] in ("long", "short")
            assert "ticker" in match and "layer" in match

    def test_expected_skills_per_layer(self):
        for layer, skills in SCENARIO["expected_skills"].items():
            assert len(skills) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/benchmark/test_scenario.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Iran escalation scenario**

Create `backend/tests/benchmark/scenarios/__init__.py` (empty).

Create `backend/tests/benchmark/scenarios/iran_escalation.py` with `SCENARIO` dict containing:
- `id`: "iran-escalation"
- `name`: "Iran Escalation — Oil & Gold"
- `description`: The causal chain summary
- `news_pool`: 3 news items (US Navy deployment, domestic political pressure, strategic timing analysis). Each with id, title, summary, url, source, tickers, sectors.
- `value_pool`: 4 instruments — USO (oil ETF), XLE (energy SPDR), GLD (gold), QQQ (tech). Each with ticker, name, sector, price, pe_ratio, market_cap, price_change_pct, score, discount_pct.
- `expected_depth`: 3
- `checkpoints`: Per-layer directional checkpoints:
  - L1: military strike, political timing (both required)
  - L2: oil price increase, Strait of Hormuz (required) + supply disruption (bonus)
  - L3: inflation from oil costs, Fed constrained (required) + USD strengthens (bonus) + gold falls (required)
- `expected_matches`: USO long at L2, GLD short at L3
- `expected_skills`: L1 geopolitical_risk, L2 supply_chain + geopolitical_risk, L3 macro_economics

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/benchmark/test_scenario.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/benchmark/scenarios/ backend/tests/benchmark/test_scenario.py
git commit -m "feat(benchmark): add Iran escalation scenario definition"
```
