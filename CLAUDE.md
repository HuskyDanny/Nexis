# Financial Agent v2 — Main Repo

## Worktree Topology

| Role | Path | Branch |
|------|------|--------|
| **Main (you)** | `~/Desktop/repos/projects/financial-agent-v2` | `main` |
| Backend | `~/Desktop/repos/projects/financial-agent-v2-backend-wt` | `wt/backend` |
| Frontend | `~/Desktop/repos/projects/financial-agent-v2-frontend-wt` | `wt/frontend` |

**You are the main repo.** This is the coordinator — all merges happen here.

### Worktree Rules
- Worktrees are **persistent** — don't delete them between tasks. To reset: `git reset --hard origin/main` inside the worktree.
- Backend worktree touches only `backend/` files.
- Frontend worktree touches only `frontend/` files.
- Each worktree runs its own Claude Code session.

### Persistent Worktree
This worktree is persistent — don't delete it between tasks. Reset with:
```bash
git fetch origin main && git reset --hard origin/main && git clean -fd
```

### Worktree Port Convention

Each worktree uses a dedicated port pair to avoid conflicts during parallel development:

| Worktree | Backend Port | Frontend Port | Vite Proxy Target |
|----------|-------------|---------------|-------------------|
| Main     | 8000        | 3000          | `:8000`           |
| Frontend | 8001        | 3001          | `:8001`           |
| Backend  | 8002        | —             | —                 |

**Backend start:** `MONGODB_URL="mongodb://localhost:27017/financial_agent_v2" uvicorn src.main:app --port <port>`

**Frontend start:** Vite reads `VITE_API_PORT` env var (defaults to `8000`). Override per-worktree:
```bash
VITE_API_PORT=8001 npm run dev
```

### Coordination
- Check backend state: `git -C ../financial-agent-v2-backend-wt log --oneline -5`
- Check frontend state: `git -C ../financial-agent-v2-frontend-wt log --oneline -5`
- Read sibling worktree files to check compatibility or merge readiness.
- Do NOT modify files in sibling worktrees — only read from them.

### Merge Protocol
- Merge one branch at a time with `--no-ff` — least-conflict branch first.
- If both branches touch the same file: merge one first, rebase the other on main.
- After merge: verify, then clean up the branch (but keep the worktree).
