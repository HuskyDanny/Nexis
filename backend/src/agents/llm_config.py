import os
from functools import lru_cache

# Disable CrewAI telemetry before import — avoids 30s timeout on unreachable endpoint
os.environ.setdefault("CREWAI_TELEMETRY", "false")

from crewai import LLM

from src.core.config import settings

SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
MAIN_MODEL = "openai/Pro/MiniMaxAI/MiniMax-M2.5"
SMALL_MODEL = "openai/Qwen/Qwen3-8B"


def _get_api_key() -> str:
    key = settings.siliconflow_api_key
    if not key:
        raise ValueError("SILICONFLOW_API_KEY is required (set in .env or environment)")
    return key


def is_llm_available() -> bool:
    return bool(settings.siliconflow_api_key)


@lru_cache(maxsize=1)
def get_main_llm() -> LLM:
    return LLM(
        model=MAIN_MODEL,
        api_key=_get_api_key(),
        base_url=SILICONFLOW_BASE_URL,
        temperature=0.3,
    )


@lru_cache(maxsize=1)
def get_small_llm() -> LLM:
    return LLM(
        model=SMALL_MODEL,
        api_key=_get_api_key(),
        base_url=SILICONFLOW_BASE_URL,
        temperature=0.1,
    )


def get_litellm_params() -> dict:
    """Return params dict for direct litellm.acompletion() calls."""
    return {
        "model": MAIN_MODEL,
        "api_key": _get_api_key(),
        "api_base": SILICONFLOW_BASE_URL,
        "temperature": 0.3,
    }
