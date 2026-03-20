# Backend Architecture

## Architecture Principles

### Skills-Based, Not MCP
Every capability is a **skill**. Each skill wraps either direct HTTP calls or pure code functions. No MCP dependency. Skills are composable and testable in isolation.

### Lifecycle Hooks
The pipeline has injectable hooks at every stage. Hooks serve as:
- **Guardrails**: Prevent LLM from proceeding in wrong direction
- **Reinforcement**: Inject context or rules when specific events occur
- **Observability**: Log, trace, alert at each lifecycle stage

### Sub-Agents with Character
Domain-specific sub-agents (news analyst, technical analyst, fundamental analyst) each have:
- Specialized tool access
- Distinct system prompts / character
- A `rules.md` file recording empirical "don'ts" — things that failed, learned over time
- Self-learning: when an agent produces a bad result, the lesson is appended to its rules

### Deterministic Math — LLM Interprets, Code Calculates
Financial calculations are **coded functions**, never LLM-generated arithmetic:
- P/E ratios, Fibonacci levels, RSI, MACD — all verified Python functions
- Data sources are crosschecked (compare API result vs calculated result)
- LLM's role: interpret the numbers, explain the story, never compute the numbers
- Test coverage mandatory on all financial math functions

## Pipeline (Twice Daily)

**Schedule** (CST):
- **08:00** — China market (Shanghai/Shenzhen open, overnight US settled)
- **21:00** — US market (US close + after-hours settle)

```
1. NEWS COLLECTOR (skill: news-fetch)
   Fetch from financial news APIs → Raw news events

2. VALUE SCANNER (skill: value-scan)
   Quantitative screening → Raw value candidates
   (coded filters, not LLM arithmetic)

3. LAYER 1 ANALYSIS (skill: analyze-impact)
   LLM sub-agents: What does this mean? What's impacted?
   → Summary, direction, affected sectors/stocks
   [HOOK: post-analysis guardrail — reject hallucinated tickers]

4. LAYER 2 VERIFICATION (skill: verify-tools)
   Coded tools: technical indicators, sentiment, fundamentals
   → Structured tool outputs (deterministic, crosschecked)
   [HOOK: crosscheck — flag if tool output contradicts Layer 1]

5. LAYER 3 SOURCES
   Attach raw articles, price history, data links

6. GRAPH BUILDER (skill: build-graph)
   Assemble nodes + edges + detect convergences
   Compute confidence scores (coded formula, not LLM)
   [HOOK: post-build — validate graph integrity]

7. EXPORT PRE-RENDER (skill: render-export)
   Pre-generate markdown for each branch
```

**Orchestration**:
- Steps 1-2 run in parallel (~2 min)
- Steps 3-5 parallelized per item, concurrency limit 10 (~15 min)
- Steps 6-7 sequential (~5 min)
- Total target: < 30 minutes
- Per-item resilience: one failure skips that node, never blocks the graph

## Data Model

| Entity | Key Fields |
|--------|-----------|
| **DailyGraph** | date, market (CN/US), status, created_at |
| **Node** | id, graph_id, type, surface_summary, direction, confidence |
| **Layer** | node_id, depth (0-3), content, tool_outputs, sources |
| **Edge** | source_node, target_node, label, relationship_type |
| **Annotation** | node_id, user_id, text, tags[], created_at |
| **PipelineRun** | date, market, duration, node_count, error_count, cost |

## API

| Endpoint | Purpose |
|----------|---------|
| `GET /api/graphs/:date` | Fetch graph (nodes + edges, surface layer only) |
| `GET /api/nodes/:id/layers` | Fetch layers 1-3 for a node |
| `POST /api/annotations` | Create annotation |
| `PATCH /api/annotations/:id` | Update annotation |
| `GET /api/exports/:format` | Fetch pre-rendered export |
| `GET /api/graphs/dates` | List available dates |
| `POST /api/auth/*` | Auth (JWT, 30min access + 7day refresh) |
| `POST /api/admin/pipeline/run` | Trigger pipeline re-run (admin) |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12 + FastAPI + MongoDB + Redis |
| **AI/LLM** | LangChain + LangGraph, Qwen/DashScope |
| **Observability** | Langfuse (LLM traces) + pipeline_runs collection |
| **Deployment** | Docker Compose (dev), K8s (prod) |

## Operational

- **Cost budget**: ~200 LLM calls/day × ~2K tokens = ~400K tokens/day. Ceiling: $5/day.
- **Redis cache**: Graph 24hr TTL, layers 1hr TTL on first access.
- **Data retention**: Graphs 90 days, annotations permanent, exports 30 days.
- **Idempotency**: Pipeline keyed by date+market. Re-run overwrites (soft-delete previous).
