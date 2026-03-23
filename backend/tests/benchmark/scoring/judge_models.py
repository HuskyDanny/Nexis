"""Judge model factory for DeepEval benchmarks.

Provides a unified factory for creating DeepEval-compatible judge LLMs
from different providers (Anthropic, OpenAI, SiliconFlow).
"""

from __future__ import annotations

import json

import litellm
from deepeval.models import DeepEvalBaseLLM


class SiliconFlowModel(DeepEvalBaseLLM):
    """DeepEval LLM wrapper for SiliconFlow models via LiteLLM."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    def load_model(self) -> "SiliconFlowModel":
        return self

    def generate(self, prompt: str, schema=None) -> str | object:
        response = litellm.completion(
            model=f"openai/{self._model_name}",
            messages=[{"role": "user", "content": prompt}],
            api_base="https://api.siliconflow.cn/v1",
        )
        content: str = response.choices[0].message.content
        if schema is not None:
            return schema.model_validate(json.loads(content))
        return content

    def a_generate(self, prompt: str, schema=None) -> str | object:
        return self.generate(prompt, schema=schema)

    def get_model_name(self) -> str:
        return self._model_name


# ---------------------------------------------------------------------------
# Lazy import helpers — avoid ImportError when a provider SDK is not installed
# ---------------------------------------------------------------------------


def _make_anthropic(model: str) -> DeepEvalBaseLLM:
    from deepeval.models import AnthropicModel  # noqa: PLC0415

    return AnthropicModel(model=model)


def _make_gpt(model: str) -> DeepEvalBaseLLM:
    from deepeval.models import GPTModel  # noqa: PLC0415

    return GPTModel(model=model)


def _make_siliconflow(model: str) -> SiliconFlowModel:
    return SiliconFlowModel(model_name=model)


# ---------------------------------------------------------------------------
# Registry: CLI name → (factory_fn, provider_model_id)
# ---------------------------------------------------------------------------

AVAILABLE_MODELS: dict[str, tuple] = {
    "claude-sonnet-4-6": ("_make_anthropic", "claude-sonnet-4-6"),
    "claude-haiku-4-5": ("_make_anthropic", "claude-haiku-4-5-20251001"),
    "gpt-4o": ("_make_gpt", "gpt-4o"),
    "qwen3-8b": ("_make_siliconflow", "Qwen/Qwen3-8B"),
    "minimax-m2.5": ("_make_siliconflow", "MiniMax/MiniMax-M1-80k"),
}

# Convenience reference for tests that want to patch individual helpers
_FACTORY_MAP = {
    "_make_anthropic": _make_anthropic,
    "_make_gpt": _make_gpt,
    "_make_siliconflow": _make_siliconflow,
}


def create_judge_model(model_name: str) -> DeepEvalBaseLLM:
    """Return a DeepEval-compatible judge LLM by CLI name.

    Raises:
        ValueError: if model_name is not in AVAILABLE_MODELS.
    """
    import sys  # noqa: PLC0415

    if model_name not in AVAILABLE_MODELS:
        raise ValueError(
            f"Unknown judge model: '{model_name}'. "
            f"Available: {sorted(AVAILABLE_MODELS)}"
        )
    factory_name, provider_model_id = AVAILABLE_MODELS[model_name]
    # Resolve through the live module so patches applied via patch.object() are honoured
    module = sys.modules[__name__]
    factory = getattr(module, factory_name)
    return factory(provider_model_id)
