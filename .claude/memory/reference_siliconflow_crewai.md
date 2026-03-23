---
name: SiliconFlow + CrewAI Setup
description: LLM provider config — SiliconFlow API with MiniMax M2.5 (main) and Qwen3-8B (small/free)
type: reference
---

**Provider:** SiliconFlow
**Base URL:** `https://api.siliconflow.cn/v1`
**Auth:** `SILICONFLOW_API_KEY` env var

| Role | Model ID | Cost |
|------|----------|------|
| Main (reasoning, tool calls) | `Pro/MiniMaxAI/MiniMax-M2.5` | 2.10/8.40 per M tokens |
| Small (summarize, classify) | `Qwen/Qwen3-8B` | Free |

CrewAI LLM config uses `openai/` prefix: `LLM(model="openai/Pro/MiniMaxAI/MiniMax-M2.5", base_url=..., api_key=...)`

This replaces the generic "LiteLLM for model flexibility" from the architecture spec with a concrete provider choice.
