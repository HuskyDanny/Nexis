# Worktree Topology & Cross-Worktree Coordination

## Layout
- **Main repo:** `~/Desktop/repos/projects/financial-agent-v2` — the origin repo
- **Frontend worktree:** `~/Desktop/repos/projects/financial-agent-v2-frontend-wt` — this workspace (branch: `wt/frontend`)
- **Backend worktree:** `~/Desktop/repos/projects/financial-agent-v2-backend-wt` — sibling workspace for backend work

All three share the same git repository. Commits in any worktree are visible to the others.

## Cross-Worktree Coordination
The user may run separate Claude Code sessions in each worktree simultaneously. Sessions can coordinate by:
- Reading files from sibling worktrees to check state or compatibility
- Checking if branches are ready to merge (`git log`, `git diff` against the other branch)
- Preparing workspace for merge (rebasing, resolving conflicts)

## Rules
- Never modify files in a sibling worktree — only read from them
- Before merging, check the other worktree's branch for uncommitted work
- Follow the merge protocol in CLAUDE.md: one at a time, `--no-ff`, least-conflict first

## Context
- **When this applies:** Any cross-worktree coordination, merge preparation, or when understanding repo layout
- **Discovered:** 2026-03-21, user established worktree topology for parallel frontend/backend development
