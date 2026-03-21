# Financial Agent v2

## Worktree Topology

This repo uses parallel git worktrees for isolated development:

| Role | Path | Branch |
|------|------|--------|
| **Main** | `~/Desktop/repos/projects/financial-agent-v2` | `main` |
| **Backend** | `~/Desktop/repos/projects/financial-agent-v2-backend-wt` | `wt/backend` |
| **Frontend** | `~/Desktop/repos/projects/financial-agent-v2-frontend-wt` | `wt/frontend` |

**You are the main worktree.** You coordinate merges and can check on the other worktrees.

### Coordination
- Check sibling worktree status: `git -C ../financial-agent-v2-backend-wt status`
- Check what they've done: `git -C ../financial-agent-v2-backend-wt log --oneline -5`
- Merge when ready: `git merge wt/backend --no-ff` then `git merge wt/frontend --no-ff`
- Backend worktree touches `backend/` only. Frontend worktree touches `frontend/` only.
- If both need to modify a shared file (types, API contracts), coordinate via main first.
