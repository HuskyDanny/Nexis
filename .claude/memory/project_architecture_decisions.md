---
name: Architecture Decisions
description: Key technology and design choices — Thinking DAG, d3-force, CrewAI, SiliconFlow
type: project
---

**Data model:** Thinking DAG (ThinkingNode/Edge/Session) — multi-layer, multi-parent DAG. Each layer = agentic step. Replaces flat DailyGraph/Node/Edge.

**Backend:** FastAPI + MongoDB + Redis. Thinking API: POST /thinking (start), POST /step (layer), PATCH /node (toggle), POST /match (opportunities), GET /events (SSE).

**Frontend:** React Flow + d3-force with `forceRadial` for concentric ring layout. Nodes constrained to rings by layer number. Premium dark glassmorphism UI.

**Agent framework:** CrewAI (Flows + Crews) with SiliconFlow API (MiniMax M2.5 main, Qwen3-8B small). Currently mock — Phase 3 wires real agents.

**Key principles:**
- LLM interprets, code calculates (deterministic convergence scoring)
- Fully agentic: agent decides what news to fetch, how to reason, which values match
- AND-semantics for cascade: node needs ALL parents selected (compound reasoning). Deselect = BFS cascade. Re-select = restore from `layer_cache` (parent-set hash memoization). See spec: `docs/superpowers/specs/2026-03-21-cascade-propagation-design.md`
- Agent transparency: fetched data appears as visible "fetch" nodes

**How to apply:** When modifying the pipeline, preserve the layered structure. Each layer boundary is a Crew kickoff. The mock functions in `backend/src/api/thinking.py` (marked with `--- Mock ---` comments) are the replacement targets.
