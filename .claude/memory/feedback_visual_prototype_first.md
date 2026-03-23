---
name: Visual Prototype First
description: User prefers seeing visual effects working with mock data before wiring real backends
type: feedback
---

When building new features, simulate the full visual flow with mock data first before implementing the real backend. "Dry run and simulate the effects first" — the user wants to see the UX working end-to-end visually before committing to backend architecture.

**Why:** Iterating on UX with real backends is slow and couples visual decisions to implementation details. Mock-first lets you validate the interaction model cheaply.

**How to apply:** For any new feature: seed mock data → build frontend interaction → verify visually → then implement the real backend. First LLM call can be real (tolerate latency), cache for subsequent runs.
