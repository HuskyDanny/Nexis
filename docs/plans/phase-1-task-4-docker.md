# Task 4: Docker Compose Dev Stack

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `Makefile`

---

- [ ] **Step 1: Create backend Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e ".[dev]"
COPY . .
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 2: Create docker-compose.yml**

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    volumes: ["./backend:/app"]
    depends_on: [mongodb, redis]
    environment:
      MONGODB_URL: mongodb://mongodb:27017/financial_agent_v2
      REDIS_URL: redis://redis:6379/0

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    volumes: ["./frontend:/app", "/app/node_modules"]

  mongodb:
    image: mongo:7.0
    ports: ["27017:27017"]
    volumes: [mongodb_data:/data/db]

  redis:
    image: redis:7.2-alpine
    ports: ["6379:6379"]
    volumes: [redis_data:/data]

volumes:
  mongodb_data:
  redis_data:
```

- [ ] **Step 3: Create Makefile**

```makefile
.PHONY: dev down logs test health

dev:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose exec backend python -m pytest tests/ -x -q

health:
	curl -s http://localhost:8000/api/health | python -m json.tool
```

- [ ] **Step 4: Run `make dev` and verify all services start**

Run: `make dev && sleep 5 && make health`
Expected: All 4 services running, health returns ok

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml Makefile backend/Dockerfile
git commit -m "feat: Docker Compose dev stack — backend, frontend, mongo, redis"
```
