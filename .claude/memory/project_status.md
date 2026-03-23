---
name: Project Status
description: Financial Agent v2 — Phase 3 complete, real agent pipeline with mock fallback
type: project
---

Phase 1 (Foundation), Phase 2 (Thinking DAG MVP), **Phase 3 (Agent Pipeline)** all complete. 64 tests passing.

Phase 3 added: CrewAI agent definitions (news ranker, effect thinker, opportunity matcher), SiliconFlow LLM config, ThinkingService with automatic mock fallback when no API key.

**Why:** Clean separation between API → Service → Agents. Mock fallback means the app works E2E without an API key for development.

**Fully real E2E verified**: Real news (Alpha Vantage) → Real LLM reasoning (CrewAI + MiniMax M2.5) → Real stock matching (Yahoo Finance). API keys in `backend/.env` (gitignored). Live endpoint: `GET /api/pools/live/:date`. Phase 4 next (auth, annotations, export, QA).
