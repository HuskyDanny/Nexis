# Batch Backend Edits via Subagent to Survive Linter Hooks

## The Trap
Editing backend files one-at-a-time across multiple tool calls. A linter hook runs after each Edit and can revert unstaged changes to match git HEAD. If you make 10 edits across 10 tool calls, a hook between calls can wipe earlier edits — you lose all work and have to re-apply everything.

## The Solution
When making multiple related backend changes, delegate to a subagent that applies ALL edits in a single focused session. The subagent completes all edits and runs tests before returning. This minimizes the window where hooks can interfere.

Alternatively, stage changes with `git add` after each critical edit to protect them from restoration.

## Context
- **When this applies:** Any multi-file backend refactoring or fix session
- **Related files:** All backend Python files under `backend/`
- **Discovered:** 2026-03-24, benchmark framework fixes — 10 backend edits were reverted by linter hook, had to re-apply via subagent
