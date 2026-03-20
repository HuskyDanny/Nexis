# Phase 4: Features & Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auth, annotations, export, quality assurance, and end-to-end integration.

**Architecture:** JWT auth, annotation persistence, markdown/image export, 3-layer QA.

**Depends on:** Phase 2 (pipeline) + Phase 3 (frontend graph)

---

## Tasks

| Task | Deliverable |
|------|-------------|
| 1: JWT Authentication | Login, register, JWT access/refresh tokens, protected routes, admin role |
| 2: Annotations API + UI | Create/edit/delete annotations, tags, persist across days, annotation editor panel |
| 3: Markdown Export | Full graph or branch → structured markdown, copy to clipboard |
| 4: Image Export | Client-side canvas render (html-to-image), surface-only or expanded options |
| 5: Date Navigation | Date picker, load previous days' graphs, crossfade transition |
| 6: Search | Ticker search across current graph, highlight matching nodes |
| 7: Production Metrics | pipeline_runs tracking, per-step scores, token/cost tracking, Langfuse integration |
| 8: Functional Smoke Tests | Fixture pipeline → valid graph, API response shape, export structure |
| 9: E2E Integration | Pipeline produces graph → API serves it → frontend renders it → export works |
| 10: Error States | Pipeline failed banner, no convergences message, first-time user overlay |

## Key Principles

- **Auth mirrors v1** — JWT pattern, bcrypt passwords, 30min access + 7day refresh
- **Annotations persist by ticker** — same stock tomorrow, your notes carry over
- **Export is instant** — markdown pre-rendered by pipeline, image rendered client-side
- **QA is built-in** — not an afterthought, integrated into pipeline and CI

## Detailed task breakdowns will be written when Phase 4 starts.
