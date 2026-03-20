# Financial Agent v2 — Design Spec

> **Status**: Reviewed
> **Date**: 2026-03-20
> **Author**: Allen Pan + Claude

## Vision

A daily financial investigation board visualized as an interactive mind map. The system runs twice daily, captures news, performs multi-layer analysis, identifies value opportunities, and presents everything as a pre-computed graph you explore each morning.

**V1 was passive** — a chatbot you had to ask questions. You didn't use it.
**V2 is active** — it works while you sleep. You open it and the thinking is already done.

## Core Concept

→ See [[core-concept]] for branch model, onion layers, and convergence detection.

## Product Architecture

→ See [[product-architecture]] for layout, node types, and interactions.

## Backend Architecture

→ See [[backend-architecture]] for pipeline, data model, API, and agent philosophy.

## Frontend Architecture

→ See [[frontend-architecture]] for component hierarchy and animation strategy.

## Scope — v2 Launch

**In scope**:
- Twice-daily mind map (08:00 CST China, 21:00 CST US) with news + value branches
- Convergence detection with confidence scoring
- 4-layer onion depth on every node
- Node annotations + tags (persist across days)
- Markdown + image export (AI-native)
- Multi-user auth (JWT)
- Date navigation (view previous days)

**Out of scope (future)**:
- Real-time streaming (twice-daily batch is sufficient)
- Portfolio/broker integration
- Infinite canvas (multi-day spatial view)
- Share links (read-only graph for non-users)
- Mobile app
- Chat interface

## Success Criteria

1. You open the app daily because it's valuable
2. Every morning, the graph is ready with overnight analysis
3. You can go from "what happened?" to "what should I do?" in under 2 minutes
4. Export is instant and AI-readable
5. It looks and feels premium — fluid, interactive, modern
