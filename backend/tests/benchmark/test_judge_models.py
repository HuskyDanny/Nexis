"""Tests for judge model factory — TDD (RED phase first)."""

from unittest.mock import patch, MagicMock
import pytest


class TestAvailableModels:
    def test_available_models_not_empty(self):
        from tests.benchmark.scoring.judge_models import AVAILABLE_MODELS

        assert len(AVAILABLE_MODELS) >= 2

    def test_available_models_lists_all(self):
        from tests.benchmark.scoring.judge_models import AVAILABLE_MODELS

        assert "claude-sonnet-4-6" in AVAILABLE_MODELS
        assert "qwen3-8b" in AVAILABLE_MODELS


class TestCreateJudgeModel:
    def test_unknown_model_raises(self):
        from tests.benchmark.scoring.judge_models import create_judge_model

        with pytest.raises(ValueError, match="Unknown judge model"):
            create_judge_model("not-a-real-model")

    def test_creates_anthropic_model(self):
        from tests.benchmark.scoring import judge_models

        mock_instance = MagicMock()
        mock_cls = MagicMock(return_value=mock_instance)

        with patch.object(judge_models, "_make_anthropic") as mock_factory:
            mock_factory.return_value = mock_instance
            result = judge_models.create_judge_model("claude-sonnet-4-6")

        mock_factory.assert_called_once_with("claude-sonnet-4-6")
        assert result is mock_instance

    def test_creates_siliconflow_model(self):
        from tests.benchmark.scoring import judge_models

        mock_instance = MagicMock()

        with patch.object(judge_models, "_make_siliconflow") as mock_factory:
            mock_factory.return_value = mock_instance
            result = judge_models.create_judge_model("qwen3-8b")

        mock_factory.assert_called_once_with("Qwen/Qwen3-8B")
        assert result is mock_instance


class TestSiliconFlowModel:
    def test_get_model_name(self):
        from tests.benchmark.scoring.judge_models import SiliconFlowModel

        model = SiliconFlowModel(model_name="Qwen/Qwen3-8B")
        assert model.get_model_name() == "Qwen/Qwen3-8B"

    def test_load_model_returns_self(self):
        from tests.benchmark.scoring.judge_models import SiliconFlowModel

        model = SiliconFlowModel(model_name="Qwen/Qwen3-8B")
        assert model.load_model() is model

    def test_a_generate_delegates_to_generate(self):
        from tests.benchmark.scoring.judge_models import SiliconFlowModel

        model = SiliconFlowModel(model_name="Qwen/Qwen3-8B")
        with patch.object(model, "generate", return_value="result") as mock_gen:
            result = model.a_generate("hello")

        mock_gen.assert_called_once_with("hello", schema=None)
        assert result == "result"

    def test_generate_calls_litellm(self):
        from tests.benchmark.scoring.judge_models import SiliconFlowModel
        import litellm

        model = SiliconFlowModel(model_name="Qwen/Qwen3-8B")
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "answer text"

        with patch.object(
            litellm, "completion", return_value=mock_response
        ) as mock_completion:
            result = model.generate("test prompt")

        mock_completion.assert_called_once_with(
            model="openai/Qwen/Qwen3-8B",
            messages=[{"role": "user", "content": "test prompt"}],
            api_base="https://api.siliconflow.cn/v1",
        )
        assert result == "answer text"

    def test_generate_with_schema_parses_json(self):
        from tests.benchmark.scoring.judge_models import SiliconFlowModel
        import litellm
        from pydantic import BaseModel

        class MySchema(BaseModel):
            score: int

        model = SiliconFlowModel(model_name="Qwen/Qwen3-8B")
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"score": 7}'

        with patch.object(litellm, "completion", return_value=mock_response):
            result = model.generate("rate this", schema=MySchema)

        assert isinstance(result, MySchema)
        assert result.score == 7
