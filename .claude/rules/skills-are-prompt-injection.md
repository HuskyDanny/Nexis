# Skills Are Prompt Injection, Not Function Calls

## The Trap
Implementing agent skills as tool calls, function registries, or code-level routers. Skills are NOT tools — they're knowledge that shapes how the agent thinks.

## The Solution
Follow the Claude Code pattern:
1. Skill descriptions in **system message** (lightweight, permanent)
2. Full skill content loaded via **tool result** into conversation context (on demand)
3. The **agent itself** decides which skills to load — no external router or pre-filter
4. Skills are **auto-discovered** from files — drop a new file, it's available

## Context
- **When this applies:** Any agent skill/expertise system
- **Related files:** `backend/src/agents/skills/`
- **Discovered:** 2026-03-22, user corrected: "the metadata is loaded into system messages, the content is loaded into user messages via tool result"
