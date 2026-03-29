# Run Docker Tests from Worktree CWD, Not Main Repo

## The Trap
Running `docker compose run --rm --no-deps backend python -m pytest ...` from the main repo directory when working in a worktree. The `docker-compose.yml` volume mount (`./backend:/app`) resolves relative to CWD — so it mounts the main repo's `backend/`, not the worktree's. Tests pass but only run the main repo's test files, missing any new/changed tests in the worktree.

## The Solution
Always `cd` to the worktree directory before running `docker compose run`:
```bash
cd /path/to/worktree && docker compose run --rm --no-deps backend python -m pytest tests/... -v
```
Use `--no-deps` to avoid port conflicts with the main repo's already-running mongodb/redis containers.

## Context
- **When this applies:** Running backend tests in any worktree via Docker
- **Related files:** `docker-compose.yml`, `backend/Dockerfile`
- **Discovered:** 2026-03-25, during PR #15 review fix — only 2/6 tests collected because Docker mounted main repo files
