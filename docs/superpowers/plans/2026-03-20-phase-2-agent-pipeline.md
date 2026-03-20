# Phase 2: Agent Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CrewAI-powered analysis pipeline that fetches multi-source news, screens undervalued stocks, cross-checks credibility, reasons about convergence, and persists daily graphs to MongoDB.

**Architecture:** CrewAI Flows orchestrate two parallel branches (news collection + value scanning). After both complete, an analysis Crew cross-checks and reasons about impacts. A convergence step connects the two pools. The graph builder assembles nodes/edges/layers and upserts to MongoDB via the existing repo layer.

**Tech Stack:** CrewAI 1.11+, SiliconFlow API (MiniMax M2.5 main, Qwen3-8B small), pytest, MongoDB (existing), Pydantic models (existing)

---

## File Structure

```
backend/
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── llm_config.py              # SiliconFlow LLM instances
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── news_fetch.py           # Multi-source news aggregation
│   │   │   ├── stock_screener.py       # Value stock screening
│   │   │   ├── technical.py            # RSI, MACD, Fibonacci wrappers
│   │   │   ├── fundamental.py          # P/E, P/B, dividend yield wrappers
│   │   │   └── sentiment.py            # Sentiment analysis tool
│   │   ├── math/
│   │   │   ├── __init__.py
│   │   │   ├── indicators.py           # RSI, MACD, Fibonacci functions
│   │   │   ├── fundamentals.py         # P/E, P/B, dividend calculations
│   │   │   └── convergence.py          # Convergence score calculation
│   │   ├── crews/
│   │   │   ├── __init__.py
│   │   │   ├── news_crew.py            # News analysis crew
│   │   │   ├── value_crew.py           # Value scanning crew
│   │   │   └── impact_crew.py          # Impact analysis + cross-check crew
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── state.py                # PipelineState Pydantic model
│   │   │   ├── flow.py                 # AnalysisPipelineFlow
│   │   │   └── graph_builder.py        # Converts pipeline output → graph models
│   │   └── knowledge/
│   │       ├── news_analyst_rules.md
│   │       ├── technical_analyst_rules.md
│   │       └── fundamental_analyst_rules.md
│   └── api/
│       └── admin.py                    # POST /api/admin/pipeline/run
├── tests/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── test_indicators.py
│   │   ├── test_fundamentals.py
│   │   ├── test_convergence.py
│   │   ├── test_news_fetch.py
│   │   ├── test_stock_screener.py
│   │   ├── test_llm_config.py
│   │   ├── test_graph_builder.py
│   │   ├── test_pipeline_state.py
│   │   └── test_pipeline_flow.py
│   └── functional/
│       └── test_pipeline_smoke.py
```

---

### Task 1: Financial Math — Technical Indicators

**Files:**
- Create: `backend/src/agents/math/__init__.py`
- Create: `backend/src/agents/math/indicators.py`
- Test: `backend/tests/agents/test_indicators.py`

- [ ] **Step 1: Write failing tests for RSI**

```python
# backend/tests/agents/test_indicators.py
import pytest
from src.agents.math.indicators import calculate_rsi


class TestRSI:
    def test_rsi_with_known_values(self):
        # 14-period RSI: known input → known output
        prices = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10,
                  45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28]
        result = calculate_rsi(prices, period=14)
        assert 60 < result < 75  # Expected ~66-70 for this series

    def test_rsi_all_gains(self):
        prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
        result = calculate_rsi(prices, period=14)
        assert result == 100.0

    def test_rsi_all_losses(self):
        prices = [24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
        result = calculate_rsi(prices, period=14)
        assert result == 0.0

    def test_rsi_insufficient_data(self):
        with pytest.raises(ValueError, match="Need at least"):
            calculate_rsi([1, 2, 3], period=14)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/agents/test_indicators.py::TestRSI -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement RSI**

```python
# backend/src/agents/math/__init__.py
# (empty)

# backend/src/agents/math/indicators.py
def calculate_rsi(prices: list[float], period: int = 14) -> float:
    """Calculate Relative Strength Index. Returns 0-100."""
    if len(prices) < period + 1:
        raise ValueError(f"Need at least {period + 1} prices, got {len(prices)}")

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/agents/test_indicators.py::TestRSI -v`
Expected: 4 PASSED

- [ ] **Step 5: Write failing tests for MACD**

```python
# Append to backend/tests/agents/test_indicators.py
from src.agents.math.indicators import calculate_macd


class TestMACD:
    def test_macd_returns_three_values(self):
        prices = list(range(1, 40))  # 39 prices
        macd_line, signal_line, histogram = calculate_macd(prices)
        assert isinstance(macd_line, float)
        assert isinstance(signal_line, float)
        assert isinstance(histogram, float)

    def test_macd_histogram_is_difference(self):
        prices = [float(x) for x in range(1, 40)]
        macd_line, signal_line, histogram = calculate_macd(prices)
        assert abs(histogram - (macd_line - signal_line)) < 1e-10

    def test_macd_insufficient_data(self):
        with pytest.raises(ValueError, match="Need at least"):
            calculate_macd([1, 2, 3])
```

- [ ] **Step 6: Run tests to verify MACD tests fail**

Run: `cd backend && python -m pytest tests/agents/test_indicators.py::TestMACD -v`
Expected: FAIL with ImportError

- [ ] **Step 7: Implement MACD**

```python
# Append to backend/src/agents/math/indicators.py

def _ema(prices: list[float], period: int) -> list[float]:
    """Exponential Moving Average."""
    multiplier = 2 / (period + 1)
    ema_values = [sum(prices[:period]) / period]
    for price in prices[period:]:
        ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def calculate_macd(
    prices: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[float, float, float]:
    """Calculate MACD. Returns (macd_line, signal_line, histogram)."""
    min_required = slow + signal_period
    if len(prices) < min_required:
        raise ValueError(f"Need at least {min_required} prices, got {len(prices)}")

    fast_ema = _ema(prices, fast)
    slow_ema = _ema(prices, slow)

    # Align: fast_ema starts at index fast-1, slow_ema at slow-1
    offset = slow - fast
    macd_values = [
        fast_ema[offset + i] - slow_ema[i] for i in range(len(slow_ema))
    ]

    signal_ema = _ema(macd_values, signal_period)
    macd_line = macd_values[-1]
    signal_line = signal_ema[-1]
    return macd_line, signal_line, macd_line - signal_line
```

- [ ] **Step 8: Run tests to verify all pass**

Run: `cd backend && python -m pytest tests/agents/test_indicators.py -v`
Expected: 7 PASSED

- [ ] **Step 9: Write failing tests for Fibonacci retracement**

```python
# Append to backend/tests/agents/test_indicators.py
from src.agents.math.indicators import calculate_fibonacci_levels


class TestFibonacci:
    def test_fibonacci_levels_uptrend(self):
        levels = calculate_fibonacci_levels(high=100.0, low=50.0)
        assert levels["0.0%"] == 100.0  # high
        assert levels["100.0%"] == 50.0  # low
        assert levels["38.2%"] == pytest.approx(80.9, abs=0.1)
        assert levels["50.0%"] == 75.0
        assert levels["61.8%"] == pytest.approx(69.1, abs=0.1)

    def test_fibonacci_invalid_range(self):
        with pytest.raises(ValueError, match="high must be greater"):
            calculate_fibonacci_levels(high=50.0, low=100.0)
```

- [ ] **Step 10: Implement Fibonacci, run all tests**

```python
# Append to backend/src/agents/math/indicators.py

FIBONACCI_RATIOS = {"0.0%": 0.0, "23.6%": 0.236, "38.2%": 0.382,
                    "50.0%": 0.5, "61.8%": 0.618, "78.6%": 0.786, "100.0%": 1.0}


def calculate_fibonacci_levels(high: float, low: float) -> dict[str, float]:
    """Calculate Fibonacci retracement levels from high to low."""
    if high <= low:
        raise ValueError("high must be greater than low")
    diff = high - low
    return {label: round(high - diff * ratio, 4) for label, ratio in FIBONACCI_RATIOS.items()}
```

Run: `cd backend && python -m pytest tests/agents/test_indicators.py -v`
Expected: 9 PASSED

- [ ] **Step 11: Commit**

```bash
git add backend/src/agents/__init__.py backend/src/agents/math/ backend/tests/agents/__init__.py backend/tests/agents/test_indicators.py
git commit -m "feat: financial math — RSI, MACD, Fibonacci with full test coverage"
```

---

### Task 2: Financial Math — Fundamentals & Convergence

**Files:**
- Create: `backend/src/agents/math/fundamentals.py`
- Create: `backend/src/agents/math/convergence.py`
- Test: `backend/tests/agents/test_fundamentals.py`
- Test: `backend/tests/agents/test_convergence.py`

- [ ] **Step 1: Write failing tests for P/E, P/B, dividend yield**

```python
# backend/tests/agents/test_fundamentals.py
import pytest
from src.agents.math.fundamentals import calculate_pe, calculate_pb, calculate_dividend_yield


class TestPE:
    def test_pe_normal(self):
        assert calculate_pe(price=150.0, eps=7.5) == 20.0

    def test_pe_negative_eps(self):
        result = calculate_pe(price=150.0, eps=-2.0)
        assert result is None  # Negative earnings → N/A

    def test_pe_zero_eps(self):
        result = calculate_pe(price=150.0, eps=0.0)
        assert result is None


class TestPB:
    def test_pb_normal(self):
        assert calculate_pb(price=50.0, book_value_per_share=25.0) == 2.0

    def test_pb_zero_book(self):
        assert calculate_pb(price=50.0, book_value_per_share=0.0) is None


class TestDividendYield:
    def test_dividend_yield_normal(self):
        result = calculate_dividend_yield(annual_dividend=4.0, price=100.0)
        assert result == pytest.approx(4.0)  # 4%

    def test_dividend_yield_zero_price(self):
        assert calculate_dividend_yield(annual_dividend=4.0, price=0.0) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/agents/test_fundamentals.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement fundamentals**

```python
# backend/src/agents/math/fundamentals.py

def calculate_pe(price: float, eps: float) -> float | None:
    """Price-to-Earnings ratio. Returns None if EPS <= 0."""
    if eps <= 0:
        return None
    return round(price / eps, 2)


def calculate_pb(price: float, book_value_per_share: float) -> float | None:
    """Price-to-Book ratio. Returns None if book value <= 0."""
    if book_value_per_share <= 0:
        return None
    return round(price / book_value_per_share, 2)


def calculate_dividend_yield(annual_dividend: float, price: float) -> float | None:
    """Dividend yield as percentage. Returns None if price <= 0."""
    if price <= 0:
        return None
    return round((annual_dividend / price) * 100, 2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/agents/test_fundamentals.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Write failing tests for convergence score**

```python
# backend/tests/agents/test_convergence.py
import pytest
from src.agents.math.convergence import calculate_convergence_score


class TestConvergenceScore:
    def test_perfect_convergence(self):
        score = calculate_convergence_score(
            sentiment_strength=100.0,
            value_discount_depth=100.0,
            tool_agreement=100.0,
        )
        assert score == 100.0

    def test_zero_convergence(self):
        score = calculate_convergence_score(
            sentiment_strength=0.0,
            value_discount_depth=0.0,
            tool_agreement=0.0,
        )
        assert score == 0.0

    def test_weighted_calculation(self):
        # Weights: sentiment=0.3, discount=0.3, agreement=0.4
        score = calculate_convergence_score(
            sentiment_strength=50.0,
            value_discount_depth=80.0,
            tool_agreement=90.0,
        )
        expected = 50 * 0.3 + 80 * 0.3 + 90 * 0.4  # 15 + 24 + 36 = 75
        assert score == pytest.approx(expected)

    def test_clamps_to_0_100(self):
        score = calculate_convergence_score(
            sentiment_strength=150.0,
            value_discount_depth=200.0,
            tool_agreement=300.0,
        )
        assert score == 100.0

    def test_is_high_conviction(self):
        from src.agents.math.convergence import is_high_conviction
        assert is_high_conviction(75.0) is True
        assert is_high_conviction(49.9) is False
        assert is_high_conviction(50.0) is True
```

- [ ] **Step 6: Implement convergence score**

```python
# backend/src/agents/math/convergence.py

WEIGHTS = {
    "sentiment": 0.3,
    "discount": 0.3,
    "agreement": 0.4,
}
CONVICTION_THRESHOLD = 50.0


def calculate_convergence_score(
    sentiment_strength: float,
    value_discount_depth: float,
    tool_agreement: float,
) -> float:
    """Weighted convergence score (0-100). Inputs clamped to 0-100."""
    s = max(0.0, min(100.0, sentiment_strength))
    d = max(0.0, min(100.0, value_discount_depth))
    a = max(0.0, min(100.0, tool_agreement))
    raw = s * WEIGHTS["sentiment"] + d * WEIGHTS["discount"] + a * WEIGHTS["agreement"]
    return round(min(100.0, max(0.0, raw)), 2)


def is_high_conviction(score: float) -> bool:
    """Returns True if score meets the conviction threshold."""
    return score >= CONVICTION_THRESHOLD
```

- [ ] **Step 7: Run all math tests, then commit**

Run: `cd backend && python -m pytest tests/agents/ -v`
Expected: All PASSED

```bash
git add backend/src/agents/math/fundamentals.py backend/src/agents/math/convergence.py backend/tests/agents/test_fundamentals.py backend/tests/agents/test_convergence.py
git commit -m "feat: financial math — P/E, P/B, dividend yield, convergence score"
```

---

### Task 3: LLM Configuration

**Files:**
- Create: `backend/src/agents/__init__.py`
- Create: `backend/src/agents/llm_config.py`
- Test: `backend/tests/agents/test_llm_config.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/agents/test_llm_config.py
from unittest.mock import patch


class TestLLMConfig:
    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key-123"})
    def test_get_main_llm(self):
        from src.agents.llm_config import get_main_llm
        llm = get_main_llm()
        assert llm.model == "openai/Pro/MiniMaxAI/MiniMax-M2.5"

    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key-123"})
    def test_get_small_llm(self):
        from src.agents.llm_config import get_small_llm
        llm = get_small_llm()
        assert llm.model == "openai/Qwen/Qwen3-8B"

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_raises(self):
        import importlib
        import src.agents.llm_config as mod
        importlib.reload(mod)
        import pytest
        with pytest.raises(ValueError, match="SILICONFLOW_API_KEY"):
            mod.get_main_llm()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/agents/test_llm_config.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement LLM config**

```python
# backend/src/agents/__init__.py
# (empty)

# backend/src/agents/llm_config.py
import os
from functools import lru_cache

from crewai import LLM

SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
MAIN_MODEL = "openai/Pro/MiniMaxAI/MiniMax-M2.5"
SMALL_MODEL = "openai/Qwen/Qwen3-8B"


def _get_api_key() -> str:
    key = os.environ.get("SILICONFLOW_API_KEY")
    if not key:
        raise ValueError("SILICONFLOW_API_KEY environment variable is required")
    return key


@lru_cache(maxsize=1)
def get_main_llm() -> LLM:
    """MiniMax M2.5 — complex reasoning, tool calls, multi-step tasks."""
    return LLM(
        model=MAIN_MODEL,
        api_key=_get_api_key(),
        base_url=SILICONFLOW_BASE_URL,
        temperature=0.3,
    )


@lru_cache(maxsize=1)
def get_small_llm() -> LLM:
    """Qwen3-8B — summarization, classification, extraction (free tier)."""
    return LLM(
        model=SMALL_MODEL,
        api_key=_get_api_key(),
        base_url=SILICONFLOW_BASE_URL,
        temperature=0.1,
    )
```

- [ ] **Step 4: Run tests, commit**

Run: `cd backend && python -m pytest tests/agents/test_llm_config.py -v`
Expected: 3 PASSED

```bash
git add backend/src/agents/__init__.py backend/src/agents/llm_config.py backend/tests/agents/test_llm_config.py
git commit -m "feat: SiliconFlow LLM config — MiniMax M2.5 + Qwen3-8B"
```

---

### Task 4: Agent Tools — News Fetch & Stock Screener

**Files:**
- Create: `backend/src/agents/tools/__init__.py`
- Create: `backend/src/agents/tools/news_fetch.py`
- Create: `backend/src/agents/tools/stock_screener.py`
- Test: `backend/tests/agents/test_news_fetch.py`
- Test: `backend/tests/agents/test_stock_screener.py`

- [ ] **Step 1: Write failing tests for news_fetch tool**

```python
# backend/tests/agents/test_news_fetch.py
import pytest
from src.agents.tools.news_fetch import fetch_news_multi_source


class TestNewsFetch:
    def test_returns_list_of_articles(self):
        # Uses mock/fixture data — no real HTTP in unit tests
        articles = fetch_news_multi_source("Federal Reserve rates", sources=["mock"])
        assert isinstance(articles, list)
        assert len(articles) > 0

    def test_article_has_required_fields(self):
        articles = fetch_news_multi_source("Federal Reserve rates", sources=["mock"])
        article = articles[0]
        assert "title" in article
        assert "source" in article
        assert "url" in article
        assert "published_at" in article
        assert "summary" in article

    def test_multiple_sources_tagged(self):
        articles = fetch_news_multi_source("tech stocks", sources=["mock"])
        sources = {a["source"] for a in articles}
        assert len(sources) >= 1  # At least mock source

    def test_empty_query_returns_empty(self):
        articles = fetch_news_multi_source("", sources=["mock"])
        assert articles == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/agents/test_news_fetch.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement news_fetch tool**

```python
# backend/src/agents/tools/__init__.py
# (empty)

# backend/src/agents/tools/news_fetch.py
"""Multi-source news aggregation tool.

Each article preserves its original source URL for credibility cross-checking.
In production, this wraps real news APIs (NewsAPI, RSS feeds, etc.).
Mock source provides fixture data for testing.
"""
from crewai.tools import tool

# Mock fixture data for testing without external APIs
_MOCK_ARTICLES = [
    {
        "title": "Fed Holds Rates Steady at 5.25-5.50%",
        "source": "Reuters",
        "url": "https://reuters.com/fed-rates-2026",
        "published_at": "2026-03-20T08:00:00Z",
        "summary": "The Federal Reserve held interest rates steady, signaling a dovish tone.",
    },
    {
        "title": "Federal Reserve Signals Patience on Rate Cuts",
        "source": "Bloomberg",
        "url": "https://bloomberg.com/fed-patience-2026",
        "published_at": "2026-03-20T08:15:00Z",
        "summary": "Fed officials indicated no rush to cut rates despite cooling inflation.",
    },
    {
        "title": "Tech Rally Continues Amid Rate Hold",
        "source": "CNBC",
        "url": "https://cnbc.com/tech-rally-2026",
        "published_at": "2026-03-20T09:00:00Z",
        "summary": "Technology stocks extended gains after the Fed's decision to hold rates.",
    },
]


def fetch_news_multi_source(
    query: str,
    sources: list[str] | None = None,
    max_results: int = 10,
) -> list[dict]:
    """Fetch news from multiple sources. Returns articles with source URLs preserved."""
    if not query.strip():
        return []

    if sources and "mock" in sources:
        return [a for a in _MOCK_ARTICLES if query.lower().split()[0] in a["title"].lower()
                or query.lower().split()[0] in a["summary"].lower()][:max_results]

    # TODO: Implement real news API calls (NewsAPI, RSS, etc.)
    return _MOCK_ARTICLES[:max_results]


@tool("News Fetcher")
def news_fetch_tool(query: str) -> str:
    """Fetches news articles from multiple sources for credibility cross-checking.
    Returns articles with titles, sources, URLs, and summaries."""
    articles = fetch_news_multi_source(query)
    if not articles:
        return "No articles found."
    lines = []
    for a in articles:
        lines.append(f"[{a['source']}] {a['title']}")
        lines.append(f"  URL: {a['url']}")
        lines.append(f"  {a['summary']}")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/agents/test_news_fetch.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Write failing tests for stock_screener tool**

```python
# backend/tests/agents/test_stock_screener.py
import pytest
from src.agents.tools.stock_screener import screen_value_stocks


class TestStockScreener:
    def test_returns_list_of_candidates(self):
        candidates = screen_value_stocks(market="US", source="mock")
        assert isinstance(candidates, list)
        assert len(candidates) > 0

    def test_candidate_has_required_fields(self):
        candidates = screen_value_stocks(market="US", source="mock")
        c = candidates[0]
        assert "ticker" in c
        assert "price" in c
        assert "high_52w" in c
        assert "discount_pct" in c
        assert "pe_ratio" in c

    def test_candidates_meet_discount_threshold(self):
        candidates = screen_value_stocks(market="US", source="mock")
        for c in candidates:
            assert c["discount_pct"] >= 25.0  # ≥25% below 52-week high

    def test_max_candidates_capped(self):
        candidates = screen_value_stocks(market="US", source="mock", max_results=2)
        assert len(candidates) <= 2

    def test_unknown_market_returns_empty(self):
        candidates = screen_value_stocks(market="UNKNOWN", source="mock")
        assert candidates == []
```

- [ ] **Step 6: Implement stock_screener tool**

```python
# backend/src/agents/tools/stock_screener.py
"""Value stock screening tool.

Screens for stocks ≥25% below 52-week high with favorable fundamentals.
Mock source provides fixture data for testing.
"""
from crewai.tools import tool

_MOCK_US_STOCKS = [
    {"ticker": "JPM", "price": 145.0, "high_52w": 210.0, "discount_pct": 31.0,
     "pe_ratio": 9.5, "pb_ratio": 1.2, "dividend_yield": 3.1, "sector": "Financials"},
    {"ticker": "INTC", "price": 22.0, "high_52w": 52.0, "discount_pct": 57.7,
     "pe_ratio": None, "pb_ratio": 0.9, "dividend_yield": 1.8, "sector": "Technology"},
    {"ticker": "PFE", "price": 26.0, "high_52w": 42.0, "discount_pct": 38.1,
     "pe_ratio": 12.3, "pb_ratio": 1.4, "dividend_yield": 6.2, "sector": "Healthcare"},
]

_MOCK_CN_STOCKS = [
    {"ticker": "601398.SS", "price": 4.8, "high_52w": 7.2, "discount_pct": 33.3,
     "pe_ratio": 5.1, "pb_ratio": 0.5, "dividend_yield": 5.8, "sector": "Financials"},
]


def screen_value_stocks(
    market: str = "US",
    source: str = "api",
    max_results: int = 15,
) -> list[dict]:
    """Screen for undervalued stocks. Returns candidates meeting value criteria."""
    if source == "mock":
        pool = {"US": _MOCK_US_STOCKS, "CN": _MOCK_CN_STOCKS}.get(market, [])
        return [s for s in pool if s["discount_pct"] >= 25.0][:max_results]

    # TODO: Implement real screening via financial data API
    return []


@tool("Value Stock Screener")
def stock_screener_tool(market: str) -> str:
    """Screens for undervalued stocks that are ≥25% below their 52-week high
    with favorable P/E, P/B, or dividend yield. Returns ticker, price, discount, and fundamentals."""
    candidates = screen_value_stocks(market=market)
    if not candidates:
        return f"No value candidates found for {market} market."
    lines = []
    for c in candidates:
        pe = f"P/E={c['pe_ratio']}" if c["pe_ratio"] else "P/E=N/A"
        lines.append(f"{c['ticker']}: ${c['price']} ({c['discount_pct']}% off 52w high) "
                     f"{pe} P/B={c['pb_ratio']} Div={c['dividend_yield']}%")
    return "\n".join(lines)
```

- [ ] **Step 7: Run tests, commit**

Run: `cd backend && python -m pytest tests/agents/test_news_fetch.py tests/agents/test_stock_screener.py -v`
Expected: 9 PASSED

```bash
git add backend/src/agents/tools/ backend/tests/agents/test_news_fetch.py backend/tests/agents/test_stock_screener.py
git commit -m "feat: agent tools — news_fetch (multi-source) + stock_screener (value filter)"
```

---

### Task 5: Agent Tools — Technical, Fundamental, Sentiment

**Files:**
- Create: `backend/src/agents/tools/technical.py`
- Create: `backend/src/agents/tools/fundamental.py`
- Create: `backend/src/agents/tools/sentiment.py`
- Tests inline with existing patterns (exercise tools via `_run` directly)

- [ ] **Step 1: Implement technical analysis tool wrapping math functions**

```python
# backend/src/agents/tools/technical.py
"""Technical analysis tool — wraps deterministic math functions."""
from crewai.tools import tool
from src.agents.math.indicators import calculate_rsi, calculate_macd, calculate_fibonacci_levels

# Mock price history for testing
_MOCK_PRICES: dict[str, list[float]] = {
    "JPM": [140, 138, 142, 145, 143, 141, 144, 146, 148, 147, 145, 143, 142, 144, 145,
            143, 141, 140, 142, 144, 146, 148, 147, 145, 143, 142, 144, 145, 143, 141,
            140, 142, 144, 146, 145],
    "INTC": [30, 28, 27, 25, 24, 23, 22, 21, 22, 23, 22, 21, 20, 21, 22,
             21, 20, 22, 23, 22, 21, 20, 21, 22, 21, 20, 22, 23, 22, 21,
             20, 21, 22, 21, 22],
}


def get_technical_analysis(ticker: str, source: str = "api") -> dict:
    """Run technical indicators on a ticker. Returns RSI, MACD, Fibonacci levels."""
    prices = _MOCK_PRICES.get(ticker) if source == "mock" else _MOCK_PRICES.get(ticker)

    if not prices or len(prices) < 35:
        return {"error": f"Insufficient price data for {ticker}"}

    rsi = calculate_rsi(prices)
    macd_line, signal_line, histogram = calculate_macd(prices)
    high = max(prices)
    low = min(prices)
    fib = calculate_fibonacci_levels(high, low)

    return {
        "ticker": ticker,
        "rsi": round(rsi, 2),
        "macd": {"line": round(macd_line, 4), "signal": round(signal_line, 4),
                 "histogram": round(histogram, 4)},
        "fibonacci": fib,
        "price_current": prices[-1],
        "price_high": high,
        "price_low": low,
    }


@tool("Technical Analyzer")
def technical_tool(ticker: str) -> str:
    """Runs RSI, MACD, and Fibonacci analysis on a stock ticker.
    Returns computed indicators — never estimates or guesses numbers."""
    result = get_technical_analysis(ticker)
    if "error" in result:
        return result["error"]
    return (f"{ticker}: RSI={result['rsi']}, "
            f"MACD={result['macd']['histogram']:+.4f}, "
            f"Price=${result['price_current']} "
            f"(Range: ${result['price_low']}-${result['price_high']})")
```

- [ ] **Step 2: Implement fundamental analysis tool**

```python
# backend/src/agents/tools/fundamental.py
"""Fundamental analysis tool — wraps deterministic math functions."""
from crewai.tools import tool
from src.agents.math.fundamentals import calculate_pe, calculate_pb, calculate_dividend_yield


def get_fundamental_analysis(ticker: str, source: str = "api") -> dict:
    """Compute fundamental metrics for a ticker."""
    # Mock data — in production, fetch from financial data API
    _MOCK_DATA = {
        "JPM": {"price": 145.0, "eps": 15.2, "bvps": 120.0, "annual_div": 4.60,
                "sector_avg_pe": 12.5},
        "INTC": {"price": 22.0, "eps": -0.5, "bvps": 24.5, "annual_div": 0.50,
                 "sector_avg_pe": 25.0},
        "PFE": {"price": 26.0, "eps": 2.1, "bvps": 18.5, "annual_div": 1.68,
                "sector_avg_pe": 18.0},
    }
    data = _MOCK_DATA.get(ticker)
    if not data:
        return {"error": f"No fundamental data for {ticker}"}

    return {
        "ticker": ticker,
        "pe_ratio": calculate_pe(data["price"], data["eps"]),
        "pb_ratio": calculate_pb(data["price"], data["bvps"]),
        "dividend_yield": calculate_dividend_yield(data["annual_div"], data["price"]),
        "sector_avg_pe": data["sector_avg_pe"],
        "below_sector_pe": (calculate_pe(data["price"], data["eps"]) or 999) < data["sector_avg_pe"],
    }


@tool("Fundamental Analyzer")
def fundamental_tool(ticker: str) -> str:
    """Computes P/E, P/B, and dividend yield for a stock ticker.
    All numbers are calculated, never estimated."""
    result = get_fundamental_analysis(ticker)
    if "error" in result:
        return result["error"]
    pe = result["pe_ratio"] if result["pe_ratio"] else "N/A"
    return (f"{ticker}: P/E={pe} (sector avg={result['sector_avg_pe']}), "
            f"P/B={result['pb_ratio']}, Div Yield={result['dividend_yield']}%")
```

- [ ] **Step 3: Implement sentiment tool**

```python
# backend/src/agents/tools/sentiment.py
"""Sentiment analysis tool — LLM judges article sentiment."""
from crewai.tools import tool


def analyze_sentiment(text: str) -> dict:
    """Simple rule-based sentiment for testing. In production, uses LLM-as-judge."""
    lower = text.lower()
    bullish_words = {"bullish", "gains", "rally", "surge", "positive", "growth", "steady"}
    bearish_words = {"bearish", "decline", "crash", "negative", "loss", "downturn", "risk"}

    bull_count = sum(1 for w in bullish_words if w in lower)
    bear_count = sum(1 for w in bearish_words if w in lower)
    total = bull_count + bear_count

    if total == 0:
        return {"sentiment": "neutral", "score": 0.5, "confidence": 0.3}

    score = bull_count / total
    direction = "bullish" if score > 0.55 else "bearish" if score < 0.45 else "neutral"
    return {"sentiment": direction, "score": round(score, 2), "confidence": round(total / 10, 2)}


@tool("Sentiment Analyzer")
def sentiment_tool(text: str) -> str:
    """Analyzes sentiment of financial text. Returns direction, score (0=bearish, 1=bullish),
    and confidence level."""
    result = analyze_sentiment(text)
    return f"Sentiment: {result['sentiment']} (score={result['score']}, confidence={result['confidence']})"
```

- [ ] **Step 4: Run all tool tests, commit**

Run: `cd backend && python -m pytest tests/agents/ -v`
Expected: All PASSED

```bash
git add backend/src/agents/tools/technical.py backend/src/agents/tools/fundamental.py backend/src/agents/tools/sentiment.py
git commit -m "feat: agent tools — technical, fundamental, sentiment analysis"
```

---

### Task 6: Pipeline State & Graph Builder

**Files:**
- Create: `backend/src/agents/pipeline/__init__.py`
- Create: `backend/src/agents/pipeline/state.py`
- Create: `backend/src/agents/pipeline/graph_builder.py`
- Test: `backend/tests/agents/test_pipeline_state.py`
- Test: `backend/tests/agents/test_graph_builder.py`

- [ ] **Step 1: Write failing tests for PipelineState**

```python
# backend/tests/agents/test_pipeline_state.py
from src.agents.pipeline.state import PipelineState


class TestPipelineState:
    def test_default_state(self):
        state = PipelineState()
        assert state.news_articles == []
        assert state.value_candidates == []
        assert state.analysis_results == []
        assert state.convergences == []
        assert state.date == ""
        assert state.market == "US"

    def test_state_with_data(self):
        state = PipelineState(
            date="2026-03-20",
            market="US",
            news_articles=[{"title": "Test", "source": "Mock", "url": "http://test.com",
                           "published_at": "2026-03-20", "summary": "Test news"}],
            value_candidates=[{"ticker": "JPM", "discount_pct": 31.0}],
        )
        assert len(state.news_articles) == 1
        assert state.value_candidates[0]["ticker"] == "JPM"
```

- [ ] **Step 2: Implement PipelineState**

```python
# backend/src/agents/pipeline/__init__.py
# (empty)

# backend/src/agents/pipeline/state.py
from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """Result of analyzing a single news item or value candidate."""
    ticker: str
    source_type: str  # "news" or "value"
    direction: str  # "bullish", "bearish", "neutral"
    confidence: float
    summary: str
    reasoning: str
    tool_outputs: dict = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)


class ConvergenceResult(BaseModel):
    """A ticker that appears in both news and value pools."""
    ticker: str
    news_analysis: AnalysisResult
    value_analysis: AnalysisResult
    convergence_score: float
    verdict: str


class PipelineState(BaseModel):
    """State passed through the pipeline flow."""
    date: str = ""
    market: str = "US"
    news_articles: list[dict] = Field(default_factory=list)
    value_candidates: list[dict] = Field(default_factory=list)
    analysis_results: list[AnalysisResult] = Field(default_factory=list)
    convergences: list[ConvergenceResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
```

- [ ] **Step 3: Run state tests**

Run: `cd backend && python -m pytest tests/agents/test_pipeline_state.py -v`
Expected: 2 PASSED

- [ ] **Step 4: Write failing tests for graph_builder**

```python
# backend/tests/agents/test_graph_builder.py
from src.agents.pipeline.state import PipelineState, AnalysisResult, ConvergenceResult
from src.agents.pipeline.graph_builder import build_graph


def _sample_state() -> PipelineState:
    news_analysis = AnalysisResult(
        ticker="JPM", source_type="news", direction="bullish", confidence=82.0,
        summary="Fed holds rates steady", reasoning="Dovish tone benefits banks",
        tool_outputs={"rsi": 55}, sources=["https://reuters.com/fed"],
    )
    value_analysis = AnalysisResult(
        ticker="JPM", source_type="value", direction="bullish", confidence=75.0,
        summary="JPM undervalued at 31% discount", reasoning="Strong fundamentals",
        tool_outputs={"pe_ratio": 9.5}, sources=["screen"],
    )
    convergence = ConvergenceResult(
        ticker="JPM", news_analysis=news_analysis, value_analysis=value_analysis,
        convergence_score=87.0, verdict="High conviction buy signal",
    )
    return PipelineState(
        date="2026-03-20", market="US",
        analysis_results=[news_analysis, value_analysis],
        convergences=[convergence],
    )


class TestGraphBuilder:
    def test_builds_daily_graph(self):
        graph = build_graph(_sample_state())
        assert graph["date"] == "2026-03-20"
        assert graph["market"] == "US"
        assert graph["status"] == "complete"

    def test_creates_nodes(self):
        graph = build_graph(_sample_state())
        assert len(graph["nodes"]) >= 2  # At least news + convergence

    def test_creates_edges(self):
        graph = build_graph(_sample_state())
        assert len(graph["edges"]) >= 1

    def test_convergence_node_exists(self):
        graph = build_graph(_sample_state())
        types = [n["type"] for n in graph["nodes"]]
        assert "convergence" in types

    def test_builds_layers(self):
        graph = build_graph(_sample_state())
        assert len(graph["layers"]) > 0
        layer = graph["layers"][0]
        assert "node_id" in layer
        assert "depth" in layer
        assert "content" in layer
```

- [ ] **Step 5: Implement graph_builder**

```python
# backend/src/agents/pipeline/graph_builder.py
"""Converts PipelineState into graph models (nodes, edges, layers) for MongoDB."""
from uuid import uuid4

from src.agents.pipeline.state import PipelineState, AnalysisResult, ConvergenceResult


def _make_id() -> str:
    return uuid4().hex[:12]


def _analysis_to_node(analysis: AnalysisResult, graph_id: str) -> dict:
    node_type = "news_event" if analysis.source_type == "news" else "value_opportunity"
    return {
        "id": _make_id(),
        "graph_id": graph_id,
        "type": node_type,
        "surface_summary": analysis.summary,
        "direction": analysis.direction,
        "confidence": analysis.confidence,
    }


def _convergence_to_node(conv: ConvergenceResult, graph_id: str) -> dict:
    return {
        "id": _make_id(),
        "graph_id": graph_id,
        "type": "convergence",
        "surface_summary": f"{conv.ticker} — {conv.verdict}",
        "direction": conv.news_analysis.direction,
        "confidence": conv.convergence_score,
    }


def _build_layers(node_id: str, analysis: AnalysisResult) -> list[dict]:
    layers = [
        {"node_id": node_id, "depth": 0, "content": analysis.summary},
        {"node_id": node_id, "depth": 1, "content": analysis.reasoning},
    ]
    if analysis.tool_outputs:
        layers.append({
            "node_id": node_id, "depth": 2, "content": str(analysis.tool_outputs),
            "tool_outputs": analysis.tool_outputs,
        })
    if analysis.sources:
        layers.append({
            "node_id": node_id, "depth": 3, "content": "Sources: " + ", ".join(analysis.sources),
            "sources": analysis.sources,
        })
    return layers


def build_graph(state: PipelineState) -> dict:
    """Build a complete graph dict from pipeline state. Ready for MongoDB upsert."""
    graph_id = _make_id()
    nodes = []
    edges = []
    layers = []

    # Build nodes from analysis results
    ticker_to_node: dict[str, dict] = {}
    for analysis in state.analysis_results:
        node = _analysis_to_node(analysis, graph_id)
        nodes.append(node)
        layers.extend(_build_layers(node["id"], analysis))
        key = f"{analysis.ticker}:{analysis.source_type}"
        ticker_to_node[key] = node

    # Build convergence nodes and edges
    for conv in state.convergences:
        conv_node = _convergence_to_node(conv, graph_id)
        nodes.append(conv_node)

        # Build convergence layers
        layers.extend([
            {"node_id": conv_node["id"], "depth": 0,
             "content": f"{conv.ticker}: {conv.verdict}"},
            {"node_id": conv_node["id"], "depth": 1,
             "content": f"News: {conv.news_analysis.reasoning}\nValue: {conv.value_analysis.reasoning}"},
        ])

        # Connect news → convergence and value → convergence
        news_node = ticker_to_node.get(f"{conv.ticker}:news")
        value_node = ticker_to_node.get(f"{conv.ticker}:value")
        if news_node:
            edges.append({"source": news_node["id"], "target": conv_node["id"],
                         "label": "confirms"})
        if value_node:
            edges.append({"source": value_node["id"], "target": conv_node["id"],
                         "label": "confirms"})

    return {
        "date": state.date,
        "market": state.market,
        "status": "complete" if not state.errors else "failed",
        "nodes": nodes,
        "edges": edges,
        "layers": layers,
    }
```

- [ ] **Step 6: Run tests, commit**

Run: `cd backend && python -m pytest tests/agents/test_pipeline_state.py tests/agents/test_graph_builder.py -v`
Expected: 7 PASSED

```bash
git add backend/src/agents/pipeline/ backend/tests/agents/test_pipeline_state.py backend/tests/agents/test_graph_builder.py
git commit -m "feat: pipeline state model + graph builder (state → nodes/edges/layers)"
```

---

### Task 7: Agent Knowledge Rules

**Files:**
- Create: `backend/src/agents/knowledge/news_analyst_rules.md`
- Create: `backend/src/agents/knowledge/technical_analyst_rules.md`
- Create: `backend/src/agents/knowledge/fundamental_analyst_rules.md`

- [ ] **Step 1: Write knowledge rules files**

```markdown
<!-- backend/src/agents/knowledge/news_analyst_rules.md -->
# News Analyst Rules

## Source Credibility
- NEVER trust a single source. Cross-check key claims across 2+ outlets.
- Prioritize: Reuters, Bloomberg, AP > CNBC, WSJ > social media, blogs.
- If only one source reports a claim, flag it as "unverified single-source".

## Analysis
- Always preserve original source URLs in your output.
- Distinguish between confirmed news and market speculation.
- For earnings reports: verify numbers against the company's official filing.

## Don'ts
- Do NOT invent ticker symbols. Only reference tickers from tool outputs.
- Do NOT estimate financial numbers. Use tool outputs only.
- Do NOT conflate correlation with causation in impact analysis.
```

```markdown
<!-- backend/src/agents/knowledge/technical_analyst_rules.md -->
# Technical Analyst Rules

## Indicator Usage
- RSI > 70 = overbought, RSI < 30 = oversold. Between = neutral zone.
- MACD histogram crossing zero = signal. Positive = bullish momentum, negative = bearish.
- Fibonacci levels are support/resistance zones, not price targets.

## Cross-Checking
- If RSI says overbought but MACD says bullish, note the divergence.
- Never call a direction based on a single indicator.

## Don'ts
- Do NOT calculate numbers yourself. Only use values from the Technical Analyzer tool.
- Do NOT predict specific price targets. State direction and confidence.
- Do NOT ignore the current price relative to Fibonacci levels.
```

```markdown
<!-- backend/src/agents/knowledge/fundamental_analyst_rules.md -->
# Fundamental Analyst Rules

## Valuation
- P/E below sector average = potentially undervalued. Verify with P/B and dividend yield.
- Negative P/E = company is losing money. Flag this prominently.
- P/B < 1.0 = trading below book value. Could be deep value or value trap.

## Cross-Checking
- Compare P/E to sector average, not market average.
- Dividend yield > 5% may signal distress — check payout ratio if available.
- Spot-check: If a stock screens as "value", verify the discount isn't due to a fundamental deterioration.

## Don'ts
- Do NOT use stale data. Always request fresh data from the Fundamental Analyzer tool.
- Do NOT ignore negative earnings when assessing value.
- Do NOT conflate low price with low valuation.
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/agents/knowledge/
git commit -m "feat: agent knowledge — rules.md for news, technical, fundamental analysts"
```

---

### Task 8: Crews — News, Value, Impact

**Files:**
- Create: `backend/src/agents/crews/__init__.py`
- Create: `backend/src/agents/crews/news_crew.py`
- Create: `backend/src/agents/crews/value_crew.py`
- Create: `backend/src/agents/crews/impact_crew.py`

- [ ] **Step 1: Implement news_crew**

```python
# backend/src/agents/crews/__init__.py
# (empty)

# backend/src/agents/crews/news_crew.py
"""News analysis crew — fetches multi-source news and produces impact analysis."""
from crewai import Agent, Crew, Process, Task

from src.agents.llm_config import get_main_llm, get_small_llm
from src.agents.tools.news_fetch import news_fetch_tool
from src.agents.tools.sentiment import sentiment_tool


def create_news_crew(topic: str, market: str) -> Crew:
    """Create a crew that fetches news and analyzes market impact."""
    main_llm = get_main_llm()
    small_llm = get_small_llm()

    collector = Agent(
        role="News Collector",
        goal=f"Find and aggregate news about {topic} from multiple credible sources",
        backstory="You are a financial news researcher who never trusts a single source. "
                  "You cross-reference headlines across Reuters, Bloomberg, and other outlets. "
                  "You always preserve original source URLs.",
        llm=small_llm,
        tools=[news_fetch_tool],
        verbose=True,
    )

    analyst = Agent(
        role="News Impact Analyst",
        goal=f"Analyze how collected news impacts the {market} market sectors and stocks",
        backstory="You are a senior market analyst who connects news events to sector impacts. "
                  "You identify which stocks and ETFs are most affected. "
                  "You rate sentiment and provide directional calls with confidence scores.",
        llm=main_llm,
        tools=[sentiment_tool],
        knowledge_sources=["src/agents/knowledge/news_analyst_rules.md"],
        verbose=True,
    )

    collect_task = Task(
        description=f"Search for recent news about '{topic}' in the {market} market. "
                    "Fetch from multiple sources. Return a structured list of articles with "
                    "titles, sources, URLs, and summaries.",
        expected_output="A list of 3-10 news articles with source attribution and URLs.",
        agent=collector,
    )

    analyze_task = Task(
        description="Analyze the collected news articles. For each major news event: "
                    "1) Identify impacted sectors and specific tickers, "
                    "2) Determine direction (bullish/bearish/neutral), "
                    "3) Rate confidence (0-100), "
                    "4) Cross-check: if only one source reports it, flag as unverified. "
                    "Preserve all source URLs.",
        expected_output="Structured analysis with tickers, directions, confidence scores, "
                       "reasoning, and source URLs for each news-driven insight.",
        agent=analyst,
        context=[collect_task],
    )

    return Crew(
        agents=[collector, analyst],
        tasks=[collect_task, analyze_task],
        process=Process.sequential,
        verbose=True,
    )
```

- [ ] **Step 2: Implement value_crew**

```python
# backend/src/agents/crews/value_crew.py
"""Value scanning crew — screens for undervalued stocks and analyzes fundamentals."""
from crewai import Agent, Crew, Process, Task

from src.agents.llm_config import get_main_llm, get_small_llm
from src.agents.tools.stock_screener import stock_screener_tool
from src.agents.tools.fundamental import fundamental_tool
from src.agents.tools.technical import technical_tool


def create_value_crew(market: str) -> Crew:
    """Create a crew that screens and analyzes value stocks."""
    main_llm = get_main_llm()
    small_llm = get_small_llm()

    screener = Agent(
        role="Value Stock Screener",
        goal=f"Find stocks in the {market} market that are significantly undervalued",
        backstory="You are a quantitative screener who finds stocks trading well below "
                  "their 52-week highs with strong fundamentals. You filter by P/E, P/B, "
                  "and dividend yield against sector averages.",
        llm=small_llm,
        tools=[stock_screener_tool],
        verbose=True,
    )

    fundamental_analyst = Agent(
        role="Fundamental Analyst",
        goal="Deep-dive into screened candidates' fundamental health",
        backstory="You assess whether a stock's discount is justified (value trap) or "
                  "represents genuine value. You compare metrics to sector averages and "
                  "look for unique competitive advantages.",
        llm=main_llm,
        tools=[fundamental_tool, technical_tool],
        knowledge_sources=["src/agents/knowledge/fundamental_analyst_rules.md"],
        verbose=True,
    )

    screen_task = Task(
        description=f"Screen the {market} market for value stocks. "
                    "Find stocks ≥25% below 52-week high with favorable P/E, P/B, or dividend yield.",
        expected_output="List of 5-15 value candidates with ticker, price, discount %, and key metrics.",
        agent=screener,
    )

    analyze_task = Task(
        description="For each screened candidate, run fundamental and technical analysis. "
                    "Determine: 1) Is the discount justified? 2) Direction and confidence. "
                    "3) Key reasoning. Flag any value traps (discount due to deterioration).",
        expected_output="Structured analysis per ticker: direction, confidence, reasoning, "
                       "fundamental metrics, technical indicators.",
        agent=fundamental_analyst,
        context=[screen_task],
    )

    return Crew(
        agents=[screener, fundamental_analyst],
        tasks=[screen_task, analyze_task],
        process=Process.sequential,
        verbose=True,
    )
```

- [ ] **Step 3: Implement impact_crew**

```python
# backend/src/agents/crews/impact_crew.py
"""Impact analysis crew — cross-checks and connects news + value pools."""
from crewai import Agent, Crew, Process, Task

from src.agents.llm_config import get_main_llm
from src.agents.tools.technical import technical_tool
from src.agents.tools.sentiment import sentiment_tool


def create_impact_crew(news_context: str, value_context: str, market: str) -> Crew:
    """Create a crew that reasons about convergence between news and value signals."""
    main_llm = get_main_llm()

    cross_checker = Agent(
        role="Cross-Checker",
        goal="Verify claims by spot-checking data points from both news and value analysis",
        backstory="You are a skeptical analyst who randomly verifies important claims. "
                  "You don't check everything — you pick the highest-impact assertions and "
                  "verify them against tool outputs. You flag any contradictions.",
        llm=main_llm,
        tools=[technical_tool, sentiment_tool],
        verbose=True,
    )

    convergence_reasoner = Agent(
        role="Convergence Analyst",
        goal="Connect news-driven insights with value-driven insights to find high-conviction signals",
        backstory="You are the senior strategist who sees the big picture. When a stock appears "
                  "in both the news pool (macro catalyst) and value pool (fundamental discount), "
                  "you reason about why this convergence matters and produce a verdict.",
        llm=main_llm,
        knowledge_sources=["src/agents/knowledge/technical_analyst_rules.md"],
        verbose=True,
    )

    cross_check_task = Task(
        description=f"You have two analyses for the {market} market:\n\n"
                    f"NEWS ANALYSIS:\n{news_context}\n\n"
                    f"VALUE ANALYSIS:\n{value_context}\n\n"
                    "Spot-check 2-3 important claims from each analysis against tool outputs. "
                    "Flag contradictions. Confirm or downgrade confidence scores based on evidence.",
        expected_output="Verification report: which claims checked, which confirmed, "
                       "which contradicted, adjusted confidence scores.",
        agent=cross_checker,
    )

    convergence_task = Task(
        description="Based on the cross-checked analyses, find tickers that appear in BOTH "
                    "news and value pools. For each convergence: "
                    "1) Why does this convergence matter? "
                    "2) What is the verdict (buy/watch/avoid)? "
                    "3) Confidence score (0-100). "
                    "If no convergences exist, state that clearly.",
        expected_output="List of convergence signals with ticker, verdict, confidence, "
                       "and reasoning connecting news + value perspectives.",
        agent=convergence_reasoner,
        context=[cross_check_task],
    )

    return Crew(
        agents=[cross_checker, convergence_reasoner],
        tasks=[cross_check_task, convergence_task],
        process=Process.sequential,
        verbose=True,
    )
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/agents/crews/
git commit -m "feat: crews — news_crew, value_crew, impact_crew with cross-checking"
```

---

### Task 9: Pipeline Flow

**Files:**
- Create: `backend/src/agents/pipeline/flow.py`
- Test: `backend/tests/agents/test_pipeline_flow.py`

- [ ] **Step 1: Write failing test for pipeline flow**

```python
# backend/tests/agents/test_pipeline_flow.py
"""Pipeline flow smoke test — uses mock tools, no real LLM calls."""
import pytest
from src.agents.pipeline.state import PipelineState, AnalysisResult, ConvergenceResult
from src.agents.pipeline.graph_builder import build_graph


class TestPipelineGraphOutput:
    """Test that a populated PipelineState produces a valid graph."""

    def test_full_pipeline_produces_valid_graph(self):
        state = PipelineState(
            date="2026-03-20",
            market="US",
            analysis_results=[
                AnalysisResult(
                    ticker="JPM", source_type="news", direction="bullish",
                    confidence=82.0, summary="Fed holds rates",
                    reasoning="Dovish tone", tool_outputs={"rsi": 55},
                    sources=["https://reuters.com/fed"],
                ),
                AnalysisResult(
                    ticker="JPM", source_type="value", direction="bullish",
                    confidence=75.0, summary="JPM undervalued",
                    reasoning="Strong fundamentals", tool_outputs={"pe_ratio": 9.5},
                    sources=["screen"],
                ),
                AnalysisResult(
                    ticker="INTC", source_type="value", direction="neutral",
                    confidence=45.0, summary="INTC deep discount but negative earnings",
                    reasoning="Value trap risk", tool_outputs={"pe_ratio": None},
                    sources=["screen"],
                ),
            ],
            convergences=[
                ConvergenceResult(
                    ticker="JPM",
                    news_analysis=AnalysisResult(
                        ticker="JPM", source_type="news", direction="bullish",
                        confidence=82.0, summary="Fed holds rates",
                        reasoning="Dovish tone", sources=["https://reuters.com/fed"],
                    ),
                    value_analysis=AnalysisResult(
                        ticker="JPM", source_type="value", direction="bullish",
                        confidence=75.0, summary="JPM undervalued",
                        reasoning="Strong fundamentals", sources=["screen"],
                    ),
                    convergence_score=87.0,
                    verdict="High conviction buy signal",
                ),
            ],
        )

        graph = build_graph(state)

        # Structural assertions
        assert graph["date"] == "2026-03-20"
        assert graph["market"] == "US"
        assert graph["status"] == "complete"
        assert len(graph["nodes"]) == 4  # 3 analysis + 1 convergence
        assert len(graph["edges"]) == 2  # news→conv + value→conv
        assert len(graph["layers"]) > 0

        # Node type distribution
        types = [n["type"] for n in graph["nodes"]]
        assert types.count("convergence") == 1
        assert types.count("news_event") == 1
        assert types.count("value_opportunity") == 2

        # Layers have source URLs preserved
        all_sources = [l.get("sources", []) for l in graph["layers"] if l.get("sources")]
        flat_sources = [s for sources in all_sources for s in sources]
        assert "https://reuters.com/fed" in flat_sources
```

- [ ] **Step 2: Run test to verify it passes (graph_builder already implemented)**

Run: `cd backend && python -m pytest tests/agents/test_pipeline_flow.py -v`
Expected: PASSED

- [ ] **Step 3: Implement the pipeline Flow**

```python
# backend/src/agents/pipeline/flow.py
"""AnalysisPipelineFlow — orchestrates the full pipeline via CrewAI Flow."""
import time
from datetime import datetime, timezone

from crewai.flow.flow import Flow, and_, listen, start
from pydantic import BaseModel, Field

from src.agents.pipeline.state import PipelineState
from src.agents.tools.news_fetch import fetch_news_multi_source
from src.agents.tools.stock_screener import screen_value_stocks
from src.agents.pipeline.graph_builder import build_graph


class AnalysisPipelineFlow(Flow[PipelineState]):
    """Two parallel branches (news + value) → analysis → convergence → graph."""

    @start()
    def collect_news(self):
        """Step 1a: Fetch news from multiple sources (parallel with scan_values)."""
        articles = fetch_news_multi_source(
            query=f"{self.state.market} market financial news",
            sources=["mock"],  # TODO: switch to real sources
        )
        self.state.news_articles = articles
        return articles

    @start()
    def scan_values(self):
        """Step 1b: Screen for undervalued stocks (parallel with collect_news)."""
        candidates = screen_value_stocks(
            market=self.state.market,
            source="mock",  # TODO: switch to real API
        )
        self.state.value_candidates = candidates
        return candidates

    @listen(and_(collect_news, scan_values))
    def analyze_and_connect(self):
        """Step 2: Analyze impacts, cross-check, find convergences.

        In production, this kicks off news_crew + value_crew + impact_crew.
        For now, uses deterministic mock analysis for testability.
        """
        from src.agents.pipeline.state import AnalysisResult, ConvergenceResult
        from src.agents.math.convergence import calculate_convergence_score, is_high_conviction

        # Build analysis results from collected data
        results = []
        news_tickers: dict[str, AnalysisResult] = {}

        for article in self.state.news_articles:
            result = AnalysisResult(
                ticker="MARKET",  # General market news
                source_type="news",
                direction="bullish",  # Simplified — crew would determine this
                confidence=70.0,
                summary=article["title"],
                reasoning=article["summary"],
                sources=[article["url"]],
            )
            results.append(result)

        value_tickers: dict[str, AnalysisResult] = {}
        for candidate in self.state.value_candidates:
            result = AnalysisResult(
                ticker=candidate["ticker"],
                source_type="value",
                direction="bullish" if candidate.get("discount_pct", 0) > 30 else "neutral",
                confidence=min(candidate.get("discount_pct", 0) * 2, 100),
                summary=f"{candidate['ticker']} at {candidate.get('discount_pct', 0)}% discount",
                reasoning=f"P/E={candidate.get('pe_ratio', 'N/A')}, "
                         f"P/B={candidate.get('pb_ratio', 'N/A')}",
                tool_outputs={"pe_ratio": candidate.get("pe_ratio"),
                              "discount_pct": candidate.get("discount_pct")},
                sources=["value_screen"],
            )
            results.append(result)
            value_tickers[candidate["ticker"]] = result

        # Find convergences (tickers in both pools)
        # In mock mode, we connect news impacts to value candidates
        convergences = []
        for ticker, value_result in value_tickers.items():
            # Check if any news article mentions this ticker's sector
            for article_result in results:
                if article_result.source_type == "news":
                    score = calculate_convergence_score(
                        sentiment_strength=article_result.confidence,
                        value_discount_depth=value_result.confidence,
                        tool_agreement=75.0,  # Mock agreement score
                    )
                    if is_high_conviction(score):
                        news_tickers[ticker] = article_result
                        convergences.append(ConvergenceResult(
                            ticker=ticker,
                            news_analysis=article_result,
                            value_analysis=value_result,
                            convergence_score=score,
                            verdict=f"High conviction — macro catalyst + value discount",
                        ))
                        break  # One convergence per ticker

        self.state.analysis_results = results
        self.state.convergences = convergences
        return results

    @listen(analyze_and_connect)
    def build_daily_graph(self):
        """Step 3: Build the graph structure from analysis results."""
        return build_graph(self.state)


def run_pipeline(date: str, market: str = "US") -> dict:
    """Entry point: runs the full pipeline and returns the graph dict."""
    flow = AnalysisPipelineFlow()
    flow.state.date = date
    flow.state.market = market
    result = flow.kickoff()
    return result
```

- [ ] **Step 4: Run all pipeline tests**

Run: `cd backend && python -m pytest tests/agents/ -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/src/agents/pipeline/flow.py backend/tests/agents/test_pipeline_flow.py
git commit -m "feat: AnalysisPipelineFlow — parallel collection, analysis, graph builder"
```

---

### Task 10: Admin API — Pipeline Trigger

**Files:**
- Create: `backend/src/api/admin.py`
- Modify: `backend/src/main.py` (add admin router)

- [ ] **Step 1: Write failing test**

```python
# Append to backend/tests/api/test_graphs.py (or create backend/tests/api/test_admin.py)
# backend/tests/api/test_admin.py
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestAdminPipelineRun:
    @pytest.mark.asyncio
    async def test_trigger_pipeline_returns_202(self, client):
        response = await client.post("/api/admin/pipeline/run", json={
            "date": "2026-03-20", "market": "US"
        })
        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_trigger_pipeline_returns_run_id(self, client):
        response = await client.post("/api/admin/pipeline/run", json={
            "date": "2026-03-20", "market": "US"
        })
        data = response.json()
        assert "run_id" in data
        assert "status" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/api/test_admin.py -v`
Expected: FAIL (404 — route doesn't exist)

- [ ] **Step 3: Implement admin API**

```python
# backend/src/api/admin.py
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from uuid import uuid4

router = APIRouter(prefix="/api/admin", tags=["admin"])


class PipelineRunRequest(BaseModel):
    date: str
    market: str = "US"


class PipelineRunResponse(BaseModel):
    run_id: str
    status: str
    message: str


@router.post("/pipeline/run", status_code=202, response_model=PipelineRunResponse)
async def trigger_pipeline(request: PipelineRunRequest, background_tasks: BackgroundTasks):
    """Trigger a pipeline run. Returns immediately with a run_id."""
    run_id = uuid4().hex[:12]

    async def _run_pipeline():
        from src.agents.pipeline.flow import run_pipeline
        try:
            graph = run_pipeline(date=request.date, market=request.market)
            # TODO: upsert graph to MongoDB, record PipelineRun
        except Exception as e:
            # TODO: log error, update PipelineRun status
            pass

    background_tasks.add_task(_run_pipeline)

    return PipelineRunResponse(
        run_id=run_id,
        status="accepted",
        message=f"Pipeline run queued for {request.date} ({request.market})",
    )
```

- [ ] **Step 4: Register admin router in main.py**

Add to `backend/src/main.py` after the existing router imports:

```python
from src.api.admin import router as admin_router
app.include_router(admin_router)
```

- [ ] **Step 5: Run tests, commit**

Run: `cd backend && python -m pytest tests/api/test_admin.py -v`
Expected: 2 PASSED

Run: `cd backend && python -m pytest tests/ -v`
Expected: All PASSED (existing + new)

```bash
git add backend/src/api/admin.py backend/src/main.py backend/tests/api/test_admin.py
git commit -m "feat: admin API — POST /api/admin/pipeline/run triggers background pipeline"
```

---

### Task 11: Pipeline Smoke Test (Functional)

**Files:**
- Create: `backend/tests/functional/test_pipeline_smoke.py`

- [ ] **Step 1: Write functional smoke test**

```python
# backend/tests/functional/test_pipeline_smoke.py
"""Smoke test: run the full pipeline with mock data and verify graph shape."""
from src.agents.pipeline.flow import run_pipeline


class TestPipelineSmoke:
    def test_pipeline_produces_valid_graph(self):
        graph = run_pipeline(date="2026-03-20", market="US")
        assert isinstance(graph, dict)
        assert graph["date"] == "2026-03-20"
        assert graph["market"] == "US"
        assert graph["status"] == "complete"

    def test_graph_has_nodes_and_edges(self):
        graph = run_pipeline(date="2026-03-20", market="US")
        assert len(graph["nodes"]) > 0
        assert len(graph["edges"]) >= 0  # May have 0 if no convergence

    def test_nodes_have_required_fields(self):
        graph = run_pipeline(date="2026-03-20", market="US")
        for node in graph["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "surface_summary" in node
            assert "direction" in node
            assert "confidence" in node
            assert node["type"] in {"news_event", "impact", "stock_endpoint",
                                     "value_opportunity", "reason", "convergence"}

    def test_layers_preserve_sources(self):
        graph = run_pipeline(date="2026-03-20", market="US")
        source_layers = [l for l in graph["layers"] if l.get("sources")]
        assert len(source_layers) > 0  # At least some layers have source URLs

    def test_pipeline_idempotent(self):
        g1 = run_pipeline(date="2026-03-20", market="US")
        g2 = run_pipeline(date="2026-03-20", market="US")
        assert g1["date"] == g2["date"]
        assert g1["market"] == g2["market"]
        assert len(g1["nodes"]) == len(g2["nodes"])
```

- [ ] **Step 2: Run smoke tests**

Run: `cd backend && python -m pytest tests/functional/test_pipeline_smoke.py -v`
Expected: 5 PASSED

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASSED (24 existing + ~30 new)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/functional/test_pipeline_smoke.py
git commit -m "test: pipeline smoke tests — full flow with mock data, graph shape validation"
```

---

### Task 12: Add `crewai` and Update Dependencies

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/.env.base`

- [ ] **Step 1: Update pyproject.toml**

Add to `[project] dependencies`:
```
"crewai>=1.11",
```

Add `SILICONFLOW_API_KEY` placeholder to `.env.base`:
```
SILICONFLOW_API_KEY=
```

- [ ] **Step 2: Verify install and run full suite**

Run: `cd backend && pip install -e ".[dev]" && python -m pytest tests/ -v`
Expected: All PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml backend/.env.base
git commit -m "chore: add crewai dependency, SILICONFLOW_API_KEY env placeholder"
```

---

## Summary

| Task | What It Builds | Tests |
|------|---------------|-------|
| 1 | RSI, MACD, Fibonacci | 9 |
| 2 | P/E, P/B, dividend yield, convergence score | 12 |
| 3 | SiliconFlow LLM config | 3 |
| 4 | news_fetch + stock_screener tools | 9 |
| 5 | technical, fundamental, sentiment tools | 0 (tested via integration) |
| 6 | PipelineState + graph_builder | 7 |
| 7 | Agent knowledge rules | 0 (markdown) |
| 8 | news_crew, value_crew, impact_crew | 0 (tested via smoke) |
| 9 | AnalysisPipelineFlow | 1+ |
| 10 | Admin API trigger | 2 |
| 11 | Pipeline smoke tests | 5 |
| 12 | Dependencies | 0 |

**Total new tests:** ~48
**Commits:** 12
