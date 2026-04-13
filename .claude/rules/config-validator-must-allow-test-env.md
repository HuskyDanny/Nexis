# Config Validator Must Allow "test" Environment

## The Trap
Adding a `@model_validator` that only allows `environment == "development"` to skip secret validation. CI sets `ENVIRONMENT=test`, which the validator treated as production — causing all test collection to fail with `ValidationError: Production environment requires secrets`.

## The Solution
Any config validator that gates on environment must allow BOTH "development" AND "test":
```python
if self.environment in ("development", "test"):
    return self  # skip production-only validation
```

Check the CI workflow (`pr-checks.yml`) for what `ENVIRONMENT` value it sets before writing environment-based validators.

## Context
- **When this applies:** Any `@model_validator` or startup check that branches on `settings.environment`
- **Related files:** `backend/src/core/config.py`, `.github/workflows/pr-checks.yml`
- **Discovered:** 2026-04-13, PR #38 CI failure — 13 test collection errors
