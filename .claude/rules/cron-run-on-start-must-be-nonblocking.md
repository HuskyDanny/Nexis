# Cron run_on_start Must Be Non-Blocking

## The Trap
Using `await self._run_job(name)` for `run_on_start=True` jobs in `CronManager.start_all()`. Pipeline handlers (news fetch, yfinance) take 10-60s. This blocks the FastAPI lifespan startup — the server accepts zero HTTP connections until all startup jobs complete. Health checks timeout, load balancers mark the instance as dead.

## The Solution
Fire `run_on_start` jobs as background tasks, not awaited:
```python
if config.run_on_start:
    asyncio.create_task(self._run_job(name))  # non-blocking
```
The overlap prevention in `_run_job` still works — `state.running = True` prevents the first periodic loop iteration from double-running.

## Context
- **When this applies:** Any startup initialization that runs potentially slow async handlers
- **Related files:** `backend/src/cron/manager.py`
- **Discovered:** 2026-04-13, live E2E — backend accepted no connections for 60s while yfinance fetched
