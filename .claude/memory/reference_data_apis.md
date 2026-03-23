---
name: Data APIs
description: Real data sources — Alpha Vantage (news/sentiment), Yahoo Finance (stocks), reused from v1 repo
type: reference
---

**News (primary)**: Perigon API — AI-native, pre-classified (topics, entities, sentiment, companies, locations, event types). Key: `PERIGON_API_KEY`. **150 calls/month, 10/day limit.** All calls cached in MongoDB (`perigon_cache` collection). Scope/impact scoring built-in.

**News (fallback)**: Alpha Vantage `NEWS_SENTIMENT` endpoint. Key: `ALPHA_VANTAGE_API_KEY`.

**Stocks**: Yahoo Finance via `yfinance` Python package. No API key needed.

**Analytical principle**: Macro-first funnel. Scope scoring (1-5): company → sector → industry → national → global. Impact scoring (1-5): routine → paradigm shift. Auto-select by `scope * impact` descending — geopolitical/macro events first.

**v1 repo**: `/Users/allenpan/Desktop/repos/projects/financial_agent` — has Alpha Vantage, Yahoo Finance, Exa, Alpaca, FRED.

**Live endpoint**: `GET /api/pools/live/:date` — Perigon → Alpha Vantage → mock.
