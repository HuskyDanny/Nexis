# Worktree Topology & Cross-Worktree Coordination

## Layout
- **Main repo:** `~/Desktop/repos/projects/financial-agent-v2` — the permanent origin repo
- **Feature worktrees:** `~/Desktop/repos/projects/financial-agent-v2-<feature>-wt/` — ephemeral, one per feature

All worktrees share the same git repository. Commits in any worktree are visible to the others.

## Ephemeral Model
Feature worktrees are created per feature and destroyed after merge. Memory is symlinked to the main repo so knowledge persists across worktrees.

```bash
# Create: bash ~/.claude/scripts/worktree-create.sh <feature> [frontend|backend]
# Destroy: bash ~/.claude/scripts/worktree-destroy.sh <feature>   (from main repo)
```

## Cross-Worktree Coordination
Multiple worktrees may run simultaneously. Sessions can coordinate by:
- Reading files from sibling worktrees to check state or compatibility
- Checking if branches are ready to merge (`git log`, `git diff` against the other branch)

## Rules
- Never modify files in a sibling worktree — only read from them
- Before merging, check the other worktree's branch for uncommitted work
- Follow the merge protocol in CLAUDE.md: one at a time, `--no-ff`, least-conflict first
- Never run `worktree-destroy.sh` from inside the worktree being destroyed

## Context
- **When this applies:** Any cross-worktree coordination, merge preparation, or when understanding repo layout
- **Discovered:** 2026-03-21, updated 2026-03-22 to ephemeral model with symlinked memory
