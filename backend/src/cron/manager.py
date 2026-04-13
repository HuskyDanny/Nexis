"""Async cron manager with job registry, retry, and overlap prevention."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable

from src.core.logger import get_logger

log = get_logger("cron.manager")


@dataclass
class JobConfig:
    """Declarative configuration for a single cron job."""

    name: str
    handler: Callable[[], Awaitable[None]]
    interval_seconds: float
    max_retries: int = 1
    retry_backoff_base: float = 2.0
    run_on_start: bool = False


@dataclass
class JobState:
    """Observable runtime state for a registered job."""

    last_run: datetime | None = None
    last_duration: float | None = None
    last_error: str | None = None
    running: bool = False
    run_count: int = 0
    error_count: int = 0


class CronManager:
    """Pure-asyncio cron scheduler with overlap prevention and retry."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobConfig] = {}
        self._state: dict[str, JobState] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def register(self, config: JobConfig) -> None:
        """Add a job to the registry. Must be called before start_all."""
        self._jobs[config.name] = config
        self._state[config.name] = JobState()
        log.info(
            "Registered cron job: %s (every %ds)", config.name, config.interval_seconds
        )

    async def start_all(self) -> None:
        """Start all registered jobs. Jobs with run_on_start fire in background (non-blocking)."""
        for name, config in self._jobs.items():
            if config.run_on_start:
                asyncio.create_task(self._run_job(name))
            self._tasks[name] = asyncio.create_task(self._loop(name))

    async def shutdown(self) -> None:
        """Cancel all running job loops and wait for them to finish."""
        for task in self._tasks.values():
            task.cancel()
        for name, task in self._tasks.items():
            try:
                await task
            except asyncio.CancelledError:
                pass
        log.info("Cron manager shutdown — cancelled %d jobs", len(self._tasks))
        self._tasks.clear()

    def get_status(self) -> dict[str, dict]:
        """Return observable state for all registered jobs."""
        return {
            name: {
                "last_run": s.last_run.isoformat() if s.last_run else None,
                "last_duration": s.last_duration,
                "last_error": s.last_error,
                "running": s.running,
                "run_count": s.run_count,
                "error_count": s.error_count,
            }
            for name, s in self._state.items()
        }

    async def _loop(self, name: str) -> None:
        """Sleep-then-run loop for a single job."""
        config = self._jobs[name]
        while True:
            await asyncio.sleep(config.interval_seconds)
            await self._run_job(name)

    async def _run_job(self, name: str) -> None:
        """Execute a job with overlap prevention and retry logic."""
        config = self._jobs[name]
        state = self._state[name]

        if state.running:
            log.warning("Skipping %s — previous run still executing", name)
            return

        state.running = True
        start = datetime.now(timezone.utc)

        for attempt in range(1 + config.max_retries):
            try:
                await config.handler()
                state.last_run = start
                state.last_duration = (
                    datetime.now(timezone.utc) - start
                ).total_seconds()
                state.last_error = None
                state.run_count += 1
                break
            except asyncio.CancelledError:
                raise  # Never swallow cancellation
            except Exception as e:
                if attempt < config.max_retries:
                    delay = config.retry_backoff_base**attempt
                    log.warning(
                        "%s failed (attempt %d/%d), retry in %.0fs: %s",
                        name,
                        attempt + 1,
                        config.max_retries + 1,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                else:
                    state.last_error = str(e)
                    state.error_count += 1
                    state.last_run = start
                    state.last_duration = (
                        datetime.now(timezone.utc) - start
                    ).total_seconds()
                    log.error("%s failed after %d attempts: %s", name, attempt + 1, e)

        state.running = False
