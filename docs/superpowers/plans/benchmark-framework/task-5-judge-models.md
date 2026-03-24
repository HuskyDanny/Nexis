### Task 5: Judge Model Factory

**Files:**
- Create: `backend/tests/benchmark/scoring/judge_models.py`
- Test: `backend/tests/benchmark/test_judge_models.py`

- [ ] **Step 1: Write failing test for judge model factory**

```python
# backend/tests/benchmark/test_judge_models.py
import pytest
from unittest.mock import patch, MagicMock
from tests.benchmark.scoring.judge_models import create_judge_model, AVAILABLE_MODELS


class TestJudgeModelFactory:
    def test_available_models_not_empty(self):
        assert len(AVAILABLE_MODELS) >= 2

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError, match="Unknown judge model"):
            create_judge_model("nonexistent-model")

    @patch("tests.benchmark.scoring.judge_models.AnthropicModel")
    def test_creates_anthropic_model(self, mock_cls):
        mock_cls.return_value = MagicMock()
        model = create_judge_model("claude-sonnet-4-6")
        mock_cls.assert_called_once()
        assert model is not None

    def test_available_models_lists_all(self):
        assert "claude-sonnet-4-6" in AVAILABLE_MODELS
        assert "qwen3-8b" in AVAILABLE_MODELS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/benchmark/test_judge_models.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement judge model factory**

Create `backend/tests/benchmark/scoring/judge_models.py` with:
- `SiliconFlowModel(DeepEvalBaseLLM)`: wraps LiteLLM for SiliconFlow models. `generate()` calls `litellm.completion()` with `api_base="https://api.siliconflow.cn/v1"`. Handles Pydantic schema output.
- Lazy import helpers: `_make_anthropic(model)`, `_make_gpt(model)`, `_make_siliconflow(model)`
- `AVAILABLE_MODELS` dict mapping CLI names to (factory, model_id) tuples:
  - "claude-sonnet-4-6", "claude-haiku-4-5", "gpt-4o", "qwen3-8b", "minimax-m2.5"
- `create_judge_model(model_name) -> DeepEvalBaseLLM`: factory function with clear error on unknown model

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/benchmark/test_judge_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/benchmark/scoring/judge_models.py backend/tests/benchmark/test_judge_models.py
git commit -m "feat(benchmark): add configurable judge model factory"
```
