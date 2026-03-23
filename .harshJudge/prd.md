# Financial Agent v2 (Nexis) — E2E PRD

## Application Type
fullstack

## Ports
| Service | Port |
|---------|------|
| Frontend (Vite) | 3000 |
| Backend (FastAPI) | 8000 |
| MongoDB | 27017 |
| Redis | 6379 |

## Main Scenarios
- V2: CAS guard prevents concurrent /step calls (409 on conflict)
- V6: Stale filtering on pools endpoint (default excludes, include_stale=true includes)
- V1: Session cache round-trip (Redis populated on write, read from cache)
- V8: Redis resilience (API works when Redis is down, non-fatal)

## Authentication
- **Login URL:** N/A (no auth yet)
- **Test Credentials:** N/A

## Tech Stack
- Frontend: React + TypeScript + Vite + React Flow + TailwindCSS
- Backend: FastAPI + Motor (MongoDB async) + redis.asyncio + Pydantic v2
- Database: MongoDB 7.0, Redis 7.2
- Testing: pytest, curl/httpie for API E2E; browser for frontend E2E

## Notes
- Fullstack app: React frontend (port 3000) + FastAPI backend (port 8000)
- Frontend uses React Flow for interactive graph visualization (thinking view)
- MongoDB database name: `financial_agent_v2`
- Redis keys: `session:{id}:meta`, `session:{id}:nodes`, `session:{id}:edges`
- Docker containers: `financial-agent-v2-mongodb-1`, `financial-agent-v2-redis-1`
- Backend: `cd backend && uvicorn src.main:app --port 8000`
- Frontend: `cd frontend && npm run dev`
