# Task 1: Backend Scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/main.py`
- Create: `backend/src/core/config.py`
- Create: `backend/.env.base`

---

- [ ] **Step 1: Create pyproject.toml with core dependencies**

```toml
[project]
name = "financial-agent-v2"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "motor>=3.6",
    "redis>=5.2",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "python-jose>=3.3",
    "bcrypt>=4.2",
    "crewai>=0.108",
    "litellm>=1.60",
    "langfuse>=3.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24", "pytest-cov>=6.0", "httpx>=0.28"]
```

- [ ] **Step 2: Create config.py with Pydantic Settings**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    environment: str = "development"
    mongodb_url: str = "mongodb://mongodb:27017/financial_agent_v2"
    redis_url: str = "redis://redis:6379/0"
    secret_key: str = "dev-secret-change-in-production"
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env.base"

settings = Settings()
```

- [ ] **Step 3: Write failing test for health endpoint**

```python
# tests/test_health.py
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_health_returns_ok():
    # Import deferred to avoid DB connection at import time
    from src.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "version" in resp.json()
```

Run: `cd backend && python -m pytest tests/test_health.py -v`
Expected: FAIL — module not found

- [ ] **Step 4: Create main.py with FastAPI app and lifespan**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.database.mongodb import mongodb
    await mongodb.connect(settings.mongodb_url)
    yield
    await mongodb.close()

app = FastAPI(title="Financial Agent v2", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 5: Create conftest.py with MongoDB mock for tests**

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture(autouse=True)
def mock_mongodb():
    """Prevent real MongoDB connection during tests."""
    with patch("src.database.mongodb.mongodb") as mock:
        mock.connect = AsyncMock()
        mock.close = AsyncMock()
        yield mock
```

- [ ] **Step 6: Create .env.base with default config values**

- [ ] **Step 7: Run health test — verify it passes**

Run: `cd backend && python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/ && git commit -m "feat: backend scaffold — FastAPI + config + health endpoint"
```
