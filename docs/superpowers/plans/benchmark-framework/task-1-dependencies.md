### Task 1: Install DeepEval & Configure Benchmark Marker

**Files:**
- Modify: `backend/pyproject.toml` — add deepeval + benchmark marker

This must run FIRST — Tasks 5-6 import from deepeval and will fail without it.

- [ ] **Step 1: Install deepeval**

Run: `cd backend && pip install deepeval`

- [ ] **Step 2: Add to pyproject.toml dev dependencies and marker**

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "httpx>=0.28",
    "deepeval>=2.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "benchmark: Benchmark tests (deselect with '-m not benchmark')",
]
```

- [ ] **Step 3: Verify deepeval imports work**

Run: `cd backend && python -c "from deepeval.metrics import GEval; from deepeval.models import DeepEvalBaseLLM; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "feat(benchmark): add deepeval dependency and benchmark marker"
```
