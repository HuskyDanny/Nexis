# Cascade Propagation with Layer Cache — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add parent-set-hash memoization to the toggle endpoint so re-selecting nodes restores cached children instantly, and adding nodes triggers agent regeneration only when the parent set changes.

**Architecture:** Three operations on the toggle endpoint: deselect (BFS cascade, already works), re-select (cache lookup + restore), add-from-pool (wipe + regenerate + cache write). Cache is a `layer_cache` dict on the session document keyed by `layer_number → parent_set_hash → {nodes, edges}`.

**Tech Stack:** Python, FastAPI, Pydantic, MongoDB (motor), pytest

**Spec:** `docs/superpowers/specs/2026-03-21-cascade-propagation-design.md`

**Prerequisite:** `cd backend && pip install -e '.[dev]'` (needs `pytest-asyncio`)

---

## Scope

This plan implements **operations 1 and 2** from the spec (deselect cascade + re-select from cache). **Operation 3 (add-from-pool with agent regeneration)** is deferred to a follow-up plan — it requires extracting `think_effects` into a reusable function callable from both `step` and `toggle`, which is a larger refactor.

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `backend/src/services/cache.py` | `parent_set_hash()` utility | **Create** |
| `backend/src/models/thinking.py` | Add `layer_cache` field to `ThinkingSession` | **Modify** (line 41-51) |
| `backend/src/api/thinking.py` | Toggle endpoint: re-select + cache write in step | **Modify** (lines 160-279) |
| `backend/tests/test_cache.py` | Unit tests for hash utility | **Create** |
| `backend/tests/test_cascade.py` | Unit tests for toggle deselect/re-select/cycle | **Create** |

---

## Tasks

Each task is a self-contained TDD unit. Execute in order.

| # | Task | Files | Detail |
|---|------|-------|--------|
| 1 | [[cascade-propagation/task-1-hash-utility]] | `cache.py`, `test_cache.py` | `parent_set_hash()` function |
| 2 | [[cascade-propagation/task-2-model-field]] | `thinking.py` model | Add `layer_cache` to session |
| 3 | [[cascade-propagation/task-3-session-init]] | `thinking.py` API | Initialize `layer_cache: {}` on create |
| 4 | [[cascade-propagation/task-4-step-cache-write]] | `thinking.py` API | Step writes to cache after generating children |
| 5 | [[cascade-propagation/task-5-reselect-cache]] | `thinking.py` API | Re-select restores cached children |
| 6 | [[cascade-propagation/task-6-deselect-regression]] | `test_cascade.py` | Verify deselect BFS unchanged |
| 7 | [[cascade-propagation/task-7-integration]] | `test_cascade.py` | Full deselect → re-select cycle |

**Note:** `conftest.py` has an `autouse=True` MongoDB mock. Test files in `test_cascade.py` re-patch the same path with `with patch(...)` — the inner patch wins. This is consistent with existing test patterns.
