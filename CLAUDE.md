# Financial Agent v2 (Nexis)

## Worktree Model

Feature worktrees are **ephemeral** — one per feature, destroyed after merge. See `~/.claude/CLAUDE.md` for the full workflow.

```bash
# Create
bash ~/.claude/scripts/worktree-create.sh <feature> [frontend|backend]

# Destroy (from main repo)
bash ~/.claude/scripts/worktree-destroy.sh <feature>
```

### Port Convention

Each worktree uses `VITE_API_PORT` to avoid port conflicts:

| Context | Backend Port | Frontend Port | Start Command |
|---------|-------------|---------------|---------------|
| Main / Docker | 8000 | 3000 | `docker compose up` |
| Feature worktree | 8001+ | 3000 | `VITE_API_PORT=8001 npm run dev` |

**Backend:** `MONGODB_URL="mongodb://localhost:27017/financial_agent_v2" uvicorn src.main:app --port <port>`

**Frontend:** `VITE_API_PORT=<backend-port> npm run dev`

### Coordination
- Check main: `git -C ../financial-agent-v2 log --oneline -5`
- Do NOT modify files outside your worktree's scope (frontend vs backend)
- If you need a new API contract or type, coordinate with main worktree first
