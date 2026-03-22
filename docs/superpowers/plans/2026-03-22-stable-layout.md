# Stable Graph Layout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent graph layout from reshuffling when toggling nodes or adding new layers — existing nodes stay in place, only new nodes get positioned.

**Architecture:** Add `fixedPositions` support to `layoutGraph` via d3-force `fx`/`fy` pinning. Split `ThinkingView.loadSession` into three paths: full rebuild (mount), style-only refresh (toggle), and incremental layout (step/match). A `positionMap` ref persists node positions across reloads.

**Tech Stack:** React, d3-force, @xyflow/react, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-22-stable-layout-design.md`

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `frontend/src/lib/layout.ts` | d3-force layout engine | **Modify** — add `fixedPositions` to options, set `fx`/`fy` |
| `frontend/src/lib/thinking-graph-builder.ts` | Session → React Flow conversion | **Modify** — pass `fixedPositions` through |
| `frontend/src/components/ThinkingView.tsx` | Main view component | **Modify** — add `positionMap`, split into 3 reload paths |

No new files. UI behavior change — verified via E2E in Task 4.

---

## Tasks

| # | Task | Files | Detail |
|---|------|-------|--------|
| 1 | [[stable-layout/task-1-fixed-positions]] | `layout.ts` | Add `fixedPositions` + `fx`/`fy` to d3-force sim |
| 2 | [[stable-layout/task-2-builder-passthrough]] | `thinking-graph-builder.ts` | Pass `fixedPositions` through to `layoutGraph` |
| 3 | [[stable-layout/task-3-thinking-view]] | `ThinkingView.tsx` | `positionMap` ref + 3 reload paths + wiring |
| 4 | [[stable-layout/task-4-e2e-verification]] | — | Manual E2E: toggle, step, match stability |
