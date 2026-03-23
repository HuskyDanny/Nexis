# Ephemeral Feature Worktrees with Symlinked Memory

## Problem

Current worktrees are persistent and role-based (frontend-wt, backend-wt). This doesn't scale for parallel features. Knowledge (Claude Code memory) is path-hashed, so each worktree gets its own isolated memory — insights learned in one worktree are invisible to others and lost when the worktree is destroyed.

## Design

Feature worktrees are **ephemeral** — created per feature, destroyed after merge. Memory is **symlinked** to the main repo's memory directory so all worktrees share one knowledge store.

### Lifecycle

1. **Create:** `worktree-create.sh <feature-name>` — creates worktree, symlinks memory, installs deps
2. **Work:** Agent works in the worktree with full access to main's memory
3. **Merge/PR:** Branch merged to main or PR created
4. **Destroy:** `worktree-destroy.sh <feature-name>` — removes worktree, cleans up symlink dir

### Naming Convention

```
<project>-<feature>-wt/     branch: wt/<feature>
```

Example:
```
financial-agent-v2/                        ← main (permanent)
financial-agent-v2-cascade-propagation-wt/ ← ephemeral
financial-agent-v2-auth-flow-wt/           ← ephemeral
```

### Memory Symlink

Claude Code resolves memory by hashing the absolute path of the working directory:

```
Working dir: /Users/allenpan/Desktop/repos/projects/financial-agent-v2-cascade-propagation-wt
Memory path: ~/.claude/projects/-Users-allenpan-Desktop-repos-projects-financial-agent-v2-cascade-propagation-wt/memory/
```

The symlink points the worktree's memory to main's memory:

```bash
ln -s ~/.claude/projects/<main-path-hash>/memory/ \
      ~/.claude/projects/<worktree-path-hash>/memory
```

This is transparent to Claude Code — it reads/writes through the symlink as if it's its own directory.

### `worktree-create.sh <feature-name> [frontend|backend]`

Usage: `worktree-create.sh cascade-propagation frontend`

```bash
#!/bin/bash
set -euo pipefail

FEATURE="$1"
TYPE="${2:-frontend}"  # positional: frontend (default) or backend
PROJECT_DIR="$(git rev-parse --show-toplevel)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"
WORKTREE_DIR="$PROJECT_DIR/../${PROJECT_NAME}-${FEATURE}-wt"
BRANCH="wt/${FEATURE}"

# 1. Create worktree from latest origin/main
git fetch origin main
git worktree add "$WORKTREE_DIR" -b "$BRANCH" origin/main

# 2. Symlink memory
MAIN_HASH=$(echo "$PROJECT_DIR" | tr '/' '-')
WT_HASH=$(echo "$(cd "$WORKTREE_DIR" && pwd)" | tr '/' '-')
CLAUDE_PROJECTS="$HOME/.claude/projects"

# Ensure main memory dir exists (may not if main repo never opened in Claude Code)
mkdir -p "$CLAUDE_PROJECTS/$MAIN_HASH/memory"
mkdir -p "$CLAUDE_PROJECTS/$WT_HASH"

# Idempotent: skip if symlink already exists (e.g., re-running after partial failure)
if [ -L "$CLAUDE_PROJECTS/$WT_HASH/memory" ]; then
  echo "Memory symlink already exists, skipping"
else
  ln -s "$CLAUDE_PROJECTS/$MAIN_HASH/memory" "$CLAUDE_PROJECTS/$WT_HASH/memory"
fi

# 3. Install deps
if [[ "$TYPE" == "frontend" ]]; then
  (cd "$WORKTREE_DIR/frontend" && npm install)
elif [[ "$TYPE" == "backend" ]]; then
  (cd "$WORKTREE_DIR/backend" && pip install -e '.[dev]')
fi

echo "Worktree created: $WORKTREE_DIR"
echo "Branch: $BRANCH"
echo "Memory symlinked to main"
```

### `worktree-destroy.sh <feature-name>`

```bash
#!/bin/bash
set -euo pipefail

FEATURE="$1"
PROJECT_DIR="$(git rev-parse --show-toplevel)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"
WORKTREE_DIR="$PROJECT_DIR/../${PROJECT_NAME}-${FEATURE}-wt"
BRANCH="wt/${FEATURE}"

# Guard: don't run from inside the worktree being destroyed
if [[ "$(pwd)" == "$(cd "$WORKTREE_DIR" 2>/dev/null && pwd)"* ]]; then
  echo "ERROR: Cannot destroy worktree while inside it. cd to main repo first."
  exit 1
fi

# 1. Safety checks
if [ -n "$(git -C "$WORKTREE_DIR" status --porcelain 2>/dev/null)" ]; then
  echo "ERROR: Worktree has uncommitted changes. Commit or stash first."
  exit 1
fi

# Check if merged (fetch first to handle GitHub PR merges)
git fetch origin main 2>/dev/null
if ! git branch --merged origin/main | grep -q "$BRANCH"; then
  echo "WARNING: Branch $BRANCH is NOT merged to origin/main."
  read -p "Destroy anyway? (y/N) " confirm
  [[ "$confirm" == "y" ]] || exit 1
fi

# 2. Compute worktree hash BEFORE removal (dir must exist to resolve path)
WT_HASH=$(echo "$(cd "$WORKTREE_DIR" && pwd)" | tr '/' '-')

# 3. Remove worktree (--force handles untracked build artifacts)
git worktree remove --force "$WORKTREE_DIR"

# 4. Clean up Claude projects dir for this worktree
# Note: rm -rf on the parent dir removes the symlink (not the target).
# This also removes conversation history for the worktree — intentional for ephemeral worktrees.
rm -rf "$HOME/.claude/projects/$WT_HASH"

# 5. Delete branch (safe — fails if unmerged)
git branch -d "$BRANCH" 2>/dev/null || echo "Branch $BRANCH not deleted (may be unmerged)"

echo "Worktree destroyed: $WORKTREE_DIR"
```

### Git-Tracked Knowledge (already shared)

These are shared via git automatically — no symlink needed:
- `CLAUDE.md` — project instructions
- `.claude/rules/` — behavioral rules

### Accepted Risks

1. **Race condition on memory writes** — two agents writing the same memory file simultaneously could corrupt it. Low risk in practice: memory files are named by topic (e.g., `project_status.md`), so different features rarely touch the same file. The real risk is `MEMORY.md` index updates (single shared file). Future mitigation: `flock` on MEMORY.md writes.
2. **MEMORY.md 200-line limit** — shared index across all worktrees. Manageable with discipline.
3. **Stale memories** — memories from destroyed worktrees persist in main's store. This is desirable (knowledge preservation).

### What's NOT in Scope

- Port assignment automation (manual, documented in CLAUDE.md)
- Automatic conflict resolution for parallel memory writes
- Migration from current persistent worktrees to ephemeral model

### Affected Files

| File | Change |
|------|--------|
| `~/.claude/scripts/worktree-create.sh` | **Create** — worktree + symlink + deps |
| `~/.claude/scripts/worktree-destroy.sh` | **Create** — safety checks + cleanup |
| `CLAUDE.md` | **Modify** — update worktree topology section |
| `~/.claude/CLAUDE.md` | **Modify** — update worktree workflow section |
