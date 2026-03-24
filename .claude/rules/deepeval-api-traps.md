# DeepEval API Traps (v3.9+)

## The Trap
Two silent failures when using DeepEval GEval and custom models:
1. `GEval(include_reason=True)` raises `unexpected keyword argument` — the parameter doesn't exist in v3.9+. GEval always populates `.reason` after `.measure()`.
2. `a_generate` on custom `DeepEvalBaseLLM` subclasses must be `async def`, not a sync function. DeepEval awaits it internally — a sync return causes `"object str can't be used in 'await' expression"`.

## The Solution
```python
# DON'T: GEval(..., include_reason=True)
# DO: just call metric.measure(test_case), then read metric.reason

# DON'T: def a_generate(self, prompt, schema=None): return self.generate(...)
# DO: async def a_generate(self, prompt, schema=None): return self.generate(...)
```

## Context
- **When this applies:** Any code using DeepEval GEval or custom DeepEvalBaseLLM
- **Related files:** `backend/tests/benchmark/scoring/llm_judge.py`, `backend/tests/benchmark/scoring/judge_models.py`
- **Discovered:** 2026-03-24, during benchmark E2E testing — Context7 docs showed include_reason as valid but installed v3.9.2 doesn't have it
