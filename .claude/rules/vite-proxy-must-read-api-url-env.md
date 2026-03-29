# Vite Proxy Must Read VITE_API_URL in Docker

## The Trap
Hardcoding `http://127.0.0.1:${port}` as the Vite proxy target. Works locally but fails in Docker — the backend is at the `backend` service hostname, not `127.0.0.1`. Pools return empty because every proxy request gets `ECONNREFUSED`.

## The Solution
`vite.config.ts` must prefer `VITE_API_URL` (set in docker-compose.yml) over localhost fallback:
```ts
const apiTarget = process.env.VITE_API_URL || `http://127.0.0.1:${apiPort}`;
```

## Context
- **When this applies:** Any change to vite.config.ts proxy settings or docker-compose frontend env
- **Related files:** `frontend/vite.config.ts`, `docker-compose.yml`
- **Discovered:** 2026-03-25, pools appeared empty on every Docker restart
