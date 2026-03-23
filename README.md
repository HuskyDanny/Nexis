# Nexis

**Where news and value converge.** An AI-powered financial investigation board that reasons through layers of market impact to find investment opportunities.

## What It Does

Nexis takes financial news and thinks through its effects layer by layer — like an analyst would, but automatically:

1. **News Pool** — Real-time news from Perigon (AI-native) with scope/impact scoring
2. **Thinking DAG** — Multi-layer reasoning: macro events → sector impacts → company signals
3. **Value Pool** — Real stock screening from Yahoo Finance (52-week discount, P/E, dividends)
4. **Convergence** — Where news-driven effects meet undervalued stocks = opportunities

Each layer is an agentic reasoning step powered by CrewAI + SiliconFlow LLM. The agent dynamically loads analytical skills (macro economics, geopolitical risk, sector rotation, etc.) based on context.

## Architecture

```
News Pool (Perigon/Alpha Vantage)
  │
  ├─ Layer 0: Seed news (highest scope × impact)
  ├─ Layer 1: Immediate effects (agent reasoning)
  ├─ Layer 2: Compounding effects
  ├─ Layer 3: Deep compounding
  │
  └─ Match: Final effects → Value Pool → Opportunities
```

**Frontend**: React + React Flow + d3-force (concentric ring visualization)
**Backend**: FastAPI + MongoDB + CrewAI + SiliconFlow LLM
**Data**: Perigon (news), Yahoo Finance (stocks), Alpha Vantage (fallback)

## Quick Start

```bash
# 1. Start infrastructure
docker compose up mongodb redis -d

# 2. Backend
cd backend
cp .env.base .env
# Add your API keys to .env:
#   SILICONFLOW_API_KEY=sk-...
#   PERIGON_API_KEY=...
pip install -e ".[dev]"
uvicorn src.main:app --port 8000

# 3. Frontend
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` — select news or click **Run Auto**.

## Key Features

- **Skill-based reasoning** — 8 analytical skills (macro, geopolitical, sector rotation, etc.) dynamically loaded by the agent based on context. Drop a new `.py` file in `backend/src/agents/skills/` to add a skill.
- **Concentric ring visualization** — nodes radiate outward by layer, force-directed layout with radial constraints
- **Scope/Impact scoring** — news ranked by macro relevance (geopolitical > national > sector > company)
- **Selective recalculation** — deselect a node, only downstream paths recompute
- **Path highlighting** — click an opportunity to trace its reasoning chain back to root news
- **Hover-to-reveal pools** — side panels slide in on hover during graph phase
- **Auto-run** — one click: auto-select top news → think 3 layers → match → opportunities

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/thinking/auto` | POST | Full auto pipeline |
| `/api/thinking` | POST | Start manual session |
| `/api/thinking/{session_id}/step` | POST | Think one layer |
| `/api/thinking/{session_id}/match` | POST | Match against value pool |
| `/api/thinking/{session_id}/node/{node_id}` | PATCH | Toggle node selection |
| `/api/pools/live/{date}` | GET | Real-time news + stocks |
| `/api/health` | GET | Health check |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, React Flow, d3-force, Tailwind v4, Motion |
| Backend | Python 3.12, FastAPI, MongoDB, Redis |
| Agents | CrewAI, SiliconFlow (MiniMax M2.5 + Qwen3-8B) |
| News | Perigon API (AI-native, pre-classified) |
| Stocks | Yahoo Finance (yfinance) |

## License

MIT
