# Phase 2: Agent Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CrewAI-powered analysis pipeline that produces daily graphs from news + value scanning.

**Architecture:** CrewAI Flows for orchestration, Crews for agent teams, LiteLLM for model flexibility.

**Tech Stack:** CrewAI, LiteLLM, pytest, Langfuse

**Depends on:** Phase 1 (data layer + API)

---

## Tasks

| Task | Deliverable |
|------|-------------|
| 1: Financial Math Library | Deterministic RSI, MACD, Fibonacci, P/E, convergence score functions with full test coverage |
| 2: Agent Tools (Skills) | news_fetch, value_scan, technical, sentiment, fundamentals — each wrapping HTTP or code |
| 3: Sub-Agents | news_analyst, technical_analyst, fundamental_analyst with roles, goals, knowledge/rules.md |
| 4: Crews | news_crew, value_crew, impact_crew — each with tasks, guardrails, callbacks |
| 5: Pipeline Flow | AnalysisPipelineFlow with parallel start, and_ sync, graph builder, export renderer |
| 6: Pipeline Integration | Admin API trigger, pipeline_runs tracking, Langfuse traces |
| 7: Agent Benchmarks | crewai test suite, regression thresholds, functional smoke tests |

## Key Principles

- **Math functions first** — all financial calculations tested before agents use them
- **Tools are pure** — each tool is testable in isolation without LLM
- **Agents have rules.md** — loaded as CrewAI knowledge, empirical don'ts
- **Guardrails on every task** — function-based (ticker validation) + LLM-based (quality check)
- **Pipeline is idempotent** — re-run for same date+market overwrites safely

## Detailed task breakdowns will be written when Phase 2 starts.
