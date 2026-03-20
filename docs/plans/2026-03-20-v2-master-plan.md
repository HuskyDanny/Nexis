# Financial Agent v2 — Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily financial investigation mind map — graph-first SPA with CrewAI-powered analysis pipeline.

**Architecture:** FastAPI + CrewAI (Flows + Crews) backend, React + React Flow + Motion frontend, MongoDB + Redis data layer. Twice-daily pipeline (08:00/21:00 CST) produces pre-computed graphs. Dark-first, animated, interactive.

**Tech Stack:** Python 3.12, FastAPI, CrewAI, LiteLLM, MongoDB, Redis | React 18+, TypeScript, Vite, Tailwind v4, React Flow, Motion, shadcn/ui, Magic UI

---

## Phases

Each phase is a self-contained sub-plan that produces working, testable software.

| Phase | Sub-Plan | Deliverable | Depends On |
|-------|----------|-------------|------------|
| **1** | [[phase-1-foundation]] | Docker dev stack, data models, CRUD API, frontend shell with React Flow placeholder | — |
| **2** | [[phase-2-agent-pipeline]] | CrewAI agents, financial math library, full analysis pipeline Flow | Phase 1 |
| **3** | [[phase-3-graph-frontend]] | Interactive mind map with custom nodes, animations, dark mode, side panel | Phase 1 |
| **4** | [[phase-4-features-integration]] | Auth, annotations, export, quality assurance, E2E verification | Phases 2+3 |

**Phases 2 and 3 can run in parallel** — backend pipeline and frontend graph are independent once Phase 1 establishes the data contract.

## File Structure

```
financial-agent-v2/
├── backend/
│   ├── src/
│   │   ├── api/                    # FastAPI routers
│   │   │   ├── graphs.py           # Graph CRUD endpoints
│   │   │   ├── nodes.py            # Node layer endpoints
│   │   │   ├── annotations.py      # Annotation endpoints
│   │   │   ├── exports.py          # Export endpoints
│   │   │   ├── auth.py             # JWT auth
│   │   │   ├── admin.py            # Admin + pipeline trigger
│   │   │   └── health.py           # Health check
│   │   ├── agents/                 # CrewAI agents
│   │   │   ├── pipeline.py         # AnalysisPipelineFlow
│   │   │   ├── crews/
│   │   │   │   ├── news_crew.py    # News analysis crew
│   │   │   │   ├── value_crew.py   # Value scanning crew
│   │   │   │   └── impact_crew.py  # Impact analysis crew
│   │   │   ├── agents/
│   │   │   │   ├── news_analyst.py
│   │   │   │   ├── technical_analyst.py
│   │   │   │   └── fundamental_analyst.py
│   │   │   ├── knowledge/          # Agent rules.md files
│   │   │   │   ├── news_rules.md
│   │   │   │   ├── technical_rules.md
│   │   │   │   └── fundamental_rules.md
│   │   │   └── tools/              # Agent tools (skills)
│   │   │       ├── news_fetch.py
│   │   │       ├── value_scan.py
│   │   │       ├── technical.py
│   │   │       ├── sentiment.py
│   │   │       └── fundamentals.py
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic Settings
│   │   │   └── math/               # Deterministic financial math
│   │   │       ├── indicators.py   # RSI, MACD, Stochastic
│   │   │       ├── fibonacci.py    # Fibonacci levels
│   │   │       ├── valuation.py    # P/E, P/B, dividend yield
│   │   │       └── convergence.py  # Confidence score calculation
│   │   ├── database/
│   │   │   ├── mongodb.py          # Connection manager
│   │   │   ├── redis.py            # Cache client
│   │   │   └── repositories/
│   │   │       ├── graph_repo.py
│   │   │       ├── node_repo.py
│   │   │       ├── annotation_repo.py
│   │   │       ├── pipeline_run_repo.py
│   │   │       └── user_repo.py
│   │   ├── models/                 # Pydantic domain models
│   │   │   ├── graph.py
│   │   │   ├── node.py
│   │   │   ├── annotation.py
│   │   │   ├── pipeline.py
│   │   │   └── user.py
│   │   ├── services/
│   │   │   ├── graph_service.py
│   │   │   ├── export_service.py
│   │   │   └── auth_service.py
│   │   └── main.py                 # FastAPI app + lifespan
│   ├── tests/
│   │   ├── math/                   # Financial math unit tests
│   │   ├── api/                    # API endpoint tests
│   │   ├── agents/                 # Agent benchmark tests
│   │   └── functional/             # Functional workflow tests
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env.base
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── graph/              # React Flow components
│   │   │   │   ├── GraphCanvas.tsx
│   │   │   │   ├── nodes/          # Custom node components
│   │   │   │   └── edges/          # Custom edge components
│   │   │   ├── panels/
│   │   │   │   ├── NodeDetailPanel.tsx
│   │   │   │   ├── LayerAccordion.tsx
│   │   │   │   └── AnnotationEditor.tsx
│   │   │   ├── layout/
│   │   │   │   ├── TopBar.tsx
│   │   │   │   └── BottomBar.tsx
│   │   │   └── export/
│   │   │       └── ExportModal.tsx
│   │   ├── hooks/
│   │   │   ├── useGraph.ts
│   │   │   ├── useNodeLayers.ts
│   │   │   └── useAnnotations.ts
│   │   ├── services/
│   │   │   └── api.ts
│   │   ├── types/
│   │   │   └── graph.ts
│   │   ├── lib/
│   │   │   └── utils.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── vite.config.ts
│   └── tsconfig.json
├── docker-compose.yml
├── Makefile
└── docs/
    ├── specs/                      # Design specs (already written)
    └── plans/                      # Implementation plans (this)
```
