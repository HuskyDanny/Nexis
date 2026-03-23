---
name: Pipeline Design Principles
description: Phase 2 agent pipeline — credibility cross-checking, two-pool model, random verification strategy
type: project
---

**Credibility is paramount.** Every news event must be sourced from multiple outlets. Original source links must be preserved through every layer. Don't verify everything — use random spot-checks on important claims (like auditing, not full coverage).

**Verification is hybrid:**
- LLM-as-judge for reasoning quality
- Coded functions for deterministic math (P/E, RSI, etc.)
- Stats from external APIs for cross-checking data points
- Common-sense sanity checks via scripts

**Two pools feed the graph:**
- **Big News pool** (top-down): major events, macro signals
- **Low-Value Unique Stocks pool** (bottom-up): undervalued stocks with distinctive fundamentals

**Convergence reasoning:** Both pools are "dragged" into a middle playground where the agent connects them — reasoning + calculation → verdicts. This is where the graph's convergence nodes come from.

**Why:** Raw news is unreliable; single-source analysis is fragile. The value is in cross-validated, multi-source verdicts with traceable provenance.

**How to apply:** Phase 2 agents need: a news aggregator (multi-source), a stock screener (value filters), a cross-checker (spot-check strategy), and a convergence reasoner (connects pools). Every node must carry source URLs through all layers.
