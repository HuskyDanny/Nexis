import os
from functools import lru_cache

from crewai import LLM

SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
MAIN_MODEL = "openai/Pro/MiniMaxAI/MiniMax-M2.5"
SMALL_MODEL = "openai/Qwen/Qwen3-8B"


def _get_api_key() -> str:
    key = os.environ.get("SILICONFLOW_API_KEY")
    if not key:
        raise ValueError("SILICONFLOW_API_KEY environment variable is required")
    return key


def is_llm_available() -> bool:
    return bool(os.environ.get("SILICONFLOW_API_KEY"))


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
