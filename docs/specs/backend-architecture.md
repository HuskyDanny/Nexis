# Backend Architecture

## Architecture Principles

### Skills-Based, Not MCP
Every capability is a **skill**. Each skill wraps either direct HTTP calls or pure code functions. No MCP dependency. Skills are composable and testable in isolation.

### Lifecycle Hooks
The pipeline has injectable hooks at every stage. Hooks serve as:
- **Guardrails**: Prevent LLM from proceeding in wrong direction (task guardrails with retry)
- **Reinforcement**: Inject context or rules when specific events occur
- **Observability**: Log, trace, alert at each lifecycle stage
- **Crosscheck**: Flag when tool output contradicts agent analysis

### Sub-Agents with Character
Domain-specific sub-agents (news analyst, technical analyst, fundamental analyst) each have:
- Specialized tool access (CrewAI Agent + tools)
- Distinct role, goal, backstory (CrewAI agent character)
- A `knowledge/rules.md` file recording empirical "don'ts" — loaded via CrewAI Agent knowledge
- Self-learning: when an agent produces a bad result, the lesson is appended to its rules

### Deterministic Math — LLM Interprets, Code Calculates
Financial calculations are **coded functions**, never LLM-generated arithmetic:
- P/E ratios, Fibonacci levels, RSI, MACD — all verified Python functions
- Data sources are crosschecked (compare API result vs calculated result)
- LLM's role: interpret the numbers, explain the story, never compute the numbers
- Test coverage mandatory on all financial math functions

## Agent Framework: CrewAI

**Decision**: CrewAI (Flows + Crews) over LangGraph/PydanticAI.

**Why**:
- Flows provide pipeline orchestration with `and_`/`or_`/`router` for parallel + conditional execution
- Agent character (role/goal/backstory) + knowledge (rules.md) is native
- Task guardrails (function + LLM-based, chained, with retries) = lifecycle hooks
- LiteLLM backend: model-agnostic (Qwen3, MiniMax 2.5, Claude, OpenAI — swap per agent)
- Built-in `crewai test` for agent benchmarking with scoring
- `@before_kickoff` / `@after_kickoff` / task `callback` = lifecycle hooks

## Pipeline (Twice Daily) — CrewAI Flow

**Schedule** (CST):
- **08:00** — China market (Shanghai/Shenzhen open, overnight US settled)
- **21:00** — US market (US close + after-hours settle)

```python
class AnalysisPipelineFlow(Flow[PipelineState]):
    @start()
    def collect_news(self):         # Step 1 (parallel)

    @start()
    def scan_values(self):          # Step 2 (parallel)

    @listen(and_(collect_news, scan_values))
    def analyze_impacts(self):      # Steps 3-5 (crew per item)
        # Crew: news_analyst + technical_analyst + fundamental_analyst
        # Task guardrails reject hallucinated tickers
        # Tool outputs crosschecked against analysis

    @listen(analyze_impacts)
    def build_graph(self):          # Step 6 (deterministic code)

    @listen(build_graph)
    def render_exports(self):       # Step 7 (deterministic code)
```

## Quality Assurance — Three Layers

### Layer 1: Benchmarks (Pre-Deploy Gate)
- `crewai test --n_iterations 5` scores each agent 1-10 on known test cases
- Financial math functions: deterministic unit tests with exact assertions
- Each tool: expected input → expected output regression tests
- **Gate**: Agent avg ≥ 7.0 or deploy blocked. Runs in CI before merge.

### Layer 2: Production Metrics (Passive Tracking)
- Per-step scores stored in `pipeline_runs`: news relevance, scanner precision, convergence accuracy
- Token usage + cost per agent per run (LiteLLM tracking + Langfuse)
- Drift detection: compare production scores vs benchmark baseline
- **Alert**: If step score drops > 15% from baseline

### Layer 3: Functional Workflows (Smoke Tests)
- Fixture news + market data → pipeline produces valid graph with expected structure
- Graph has correct node types, edges, convergence detection
- Export produces valid markdown structure
- API returns correct response shapes
- **No LLM quality testing** — just plumbing verification

## Data Model

| Entity | Key Fields |
|--------|-----------|
| **DailyGraph** | date, market (CN/US), status, created_at |
| **Node** | id, graph_id, type, surface_summary, direction, confidence |
| **Layer** | node_id, depth (0-3), content, tool_outputs, sources |
| **Edge** | source_node, target_node, label, relationship_type |
| **Annotation** | node_id, user_id, text, tags[], created_at |
| **PipelineRun** | date, market, duration, node_count, error_count, cost, step_scores |

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
| **Agent Framework** | CrewAI (Flows + Crews) |
| **LLM Provider** | LiteLLM (Qwen3, MiniMax 2.5, Claude, configurable per agent) |
| **Observability** | Langfuse (LLM traces) + pipeline_runs collection |
| **Testing** | crewai test (agent benchmarks) + pytest (functional + math) |
| **Deployment** | Docker Compose (dev), K8s (prod) |

## Operational

- **Cost budget**: ~200 LLM calls/day × ~2K tokens = ~400K tokens/day. Ceiling: $5/day.
- **Redis cache**: Graph 24hr TTL, layers 1hr TTL on first access.
- **Data retention**: Graphs 90 days, annotations permanent, exports 30 days.
- **Idempotency**: Pipeline keyed by date+market. Re-run overwrites (soft-delete previous).
