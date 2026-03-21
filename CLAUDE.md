# Financial Agent v2 — Frontend Worktree

## Worktree Topology

| Role | Path | Branch |
|------|------|--------|
| Main | `~/Desktop/repos/projects/financial-agent-v2` | `main` |
| Backend | `~/Desktop/repos/projects/financial-agent-v2-backend-wt` | `wt/backend` |
| **Frontend (you)** | `~/Desktop/repos/projects/financial-agent-v2-frontend-wt` | `wt/frontend` |

**You are the frontend worktree.** Only modify files under `frontend/`.

### Coordination
- Check main: `git -C ../financial-agent-v2 log --oneline -5`
- Check backend worktree: `git -C ../financial-agent-v2-backend-wt log --oneline -5`
- Do NOT modify `backend/` files — that's the backend worktree's job.
- If you need a new API contract or type, coordinate with main worktree first.
