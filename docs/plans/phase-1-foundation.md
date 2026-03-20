# Phase 1: Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standing dev environment with Docker, data models, CRUD API, and frontend shell.

**Architecture:** FastAPI + MongoDB + Redis backend, React + Vite + Tailwind v4 frontend, Docker Compose orchestration.

**Tech Stack:** Python 3.12, FastAPI, Motor, Redis, Pydantic | React 18, TypeScript, Vite, Tailwind v4, React Flow, Motion, shadcn/ui

---

## Tasks

| Task | Sub-Plan | Deliverable |
|------|----------|-------------|
| 1 | [[phase-1-task-1-backend-scaffold]] | FastAPI app, config, health endpoint |
| 2 | [[phase-1-task-2-data-layer]] | MongoDB, Redis, Pydantic models, repositories |
| 3 | [[phase-1-task-3-graph-api]] | Graph + node API endpoints with tests |
| 4 | [[phase-1-task-4-docker]] | Docker Compose dev stack, Makefile |
| 5 | [[phase-1-task-5-frontend-scaffold]] | Vite + Tailwind v4 + React Flow + shadcn shell |
| 6 | [[phase-1-task-6-contract-verification]] | Backend/frontend type alignment tests |

## Phase 1 Complete Checklist

- [ ] Backend: FastAPI starts, health endpoint works
- [ ] Database: MongoDB + Redis connected, models validated
- [ ] API: GET /api/graphs/:date, GET /api/nodes/:id/layers, GET /api/graphs/dates
- [ ] Docker: `make dev` starts all 4 services
- [ ] Frontend: Vite + Tailwind v4 + React Flow + shadcn initialized
- [ ] Types: Backend models and frontend types aligned
- [ ] Tests: Model tests + API tests + contract tests pass
