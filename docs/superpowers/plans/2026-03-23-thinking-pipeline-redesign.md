# Thinking Pipeline Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-pass thinking pipeline with a three-agent-per-layer loop (Thinker/Matcher/Controller) that matches at every layer, carries context via chain summaries, and terminates intelligently.

**Architecture:** Each layer runs Thinker → Matcher → Controller in sequence. Controller produces a chain summary for the next Thinker and decides whether to continue. Opportunities are discovered at every layer, not just the last. Any node at an earlier layer can parent any node at a later layer.

**Tech Stack:** CrewAI agents, SiliconFlow MiniMax-M2.5 (main) / Qwen3-8B (small), FastAPI, MongoDB, React Flow

**Spec:** `docs/superpowers/specs/2026-03-23-thinking-pipeline-redesign.md`

**Out of scope:** Frontend DAG rendering update (opportunities at multiple layer rings) — separate follow-up task.

**Rollback:** Each task produces a commit. Revert commits to restore previous behavior. Feature branch isolates risk.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/src/agents/thinking_crew.py` | Rewrite | Three agent functions: `run_thinker()`, `run_matcher()`, `run_controller()` + `convergence_score()` |
| `backend/src/agents/skills/base.py` | Modify | Add `allowed_skills` param to `build_system_prompt()` |
| `backend/src/agents/llm_config.py` | Modify | Read from `settings` instead of `os.environ` |
| `backend/src/services/thinking_service.py` | Rewrite | Pipeline orchestrator: `run_layer()`, `run_pipeline()`. No mock fallback. |
| `backend/src/api/thinking.py` | Modify | Update `think_step()`, `auto_think()`, `_run_pipeline()`. Add timeout, stuck cleanup. |
| `backend/src/api/pools.py` | Modify | Cache-first logic in `get_live_pools()` |
| `backend/src/main.py` | Modify | Stuck session cleanup on startup |
| `frontend/src/App.tsx` | Modify | Loading spinner for pool fetch |
| `backend/tests/test_thinking_agents.py` | Create | Unit tests for Thinker, Matcher, Controller |
| `backend/tests/test_thinking_pipeline.py` | Create | Integration tests for pipeline loop |
| `backend/tests/test_pool_cache.py` | Create | Pool cache-first logic tests |

---

## Task Overview

| Task | Description | Detail | Parallel? |
|------|------------|--------|-----------|
| 1 | Fix `llm_config.py` env var + skill filtering | Below | Independent |
| 2 | Rewrite `thinking_crew.py` — three agents | [[tasks-2-4]] | Sequential (2→3→4) |
| 3 | Rewrite `thinking_service.py` — orchestrator | [[tasks-2-4]] | Depends on 2 |
| 4 | Update API endpoints — `thinking.py` | [[tasks-2-4]] | Depends on 3 |
| 5 | Fix pool cache + loading UX | [[tasks-5-7]] | Independent |
| 6 | Fix layer cache key mismatch | [[tasks-5-7]] | Independent |
| 7 | E2E verification | [[tasks-5-7]] | Depends on all |

**Parallelization:** Tasks 1, 5, 6 are independent and can run in parallel worktrees. Tasks 2→3→4 are sequential. Task 7 depends on all others.

---

## Task 1: Fix `llm_config.py` env var bug + skill filtering

**Files:**
- Modify: `backend/src/agents/llm_config.py:11-19`
- Modify: `backend/src/agents/skills/base.py:20-44`
- Modify: `backend/src/agents/skills/__init__.py:34-37`
- Test: `backend/tests/test_skills.py`

- [ ] **Step 1: Write test for `build_system_prompt` with `allowed_skills` filter**

```python
# In backend/tests/test_skills.py — add test
def test_build_system_prompt_filters_skills():
    from src.agents.skills.base import build_system_prompt
    prompt = build_system_prompt(allowed_skills=["macro_economics"])
    assert "macro_economics" in prompt
    assert "company_fundamentals" not in prompt

def test_build_system_prompt_all_skills_when_none():
    from src.agents.skills.base import build_system_prompt
    prompt = build_system_prompt(allowed_skills=None)
    assert "macro_economics" in prompt
    assert "company_fundamentals" in prompt
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd backend && python -m pytest tests/test_skills.py -v -k "filter"` — Expected: FAIL

- [ ] **Step 3: Implement `allowed_skills` param in `build_system_prompt`**

In `base.py`, change `build_system_prompt()` to accept `allowed_skills: list[str] | None = None`. In `__init__.py`, add `get_descriptions_for(skill_names)` that filters.

- [ ] **Step 4: Fix `llm_config.py` to use settings**

Replace `os.environ.get("SILICONFLOW_API_KEY")` with `settings.siliconflow_api_key` from `src.core.config`.

- [ ] **Step 5: Run all tests — verify pass**

Run: `cd backend && python -m pytest tests/test_skills.py -v` — Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/agents/llm_config.py backend/src/agents/skills/base.py backend/src/agents/skills/__init__.py backend/tests/test_skills.py
git commit -m "fix: llm_config reads settings, build_system_prompt supports skill filtering"
```
