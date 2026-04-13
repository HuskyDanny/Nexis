"""Tests for the async cron manager."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.cron.manager import CronManager, JobConfig


@pytest.fixture()
def manager() -> CronManager:
    return CronManager()


class TestJobRegistration:
    def test_register_adds_job_and_state(self, manager: CronManager) -> None:
        handler = AsyncMock()
        config = JobConfig(name="test_job", handler=handler, interval_seconds=60)
        manager.register(config)

        assert "test_job" in manager._jobs
        assert "test_job" in manager._state
        assert manager._state["test_job"].run_count == 0

    def test_register_multiple_jobs(self, manager: CronManager) -> None:
        for i in range(3):
            manager.register(
                JobConfig(name=f"job_{i}", handler=AsyncMock(), interval_seconds=60)
            )
        assert len(manager._jobs) == 3

    def test_get_status_empty(self, manager: CronManager) -> None:
        assert manager.get_status() == {}

    def test_get_status_after_register(self, manager: CronManager) -> None:
        manager.register(JobConfig(name="j", handler=AsyncMock(), interval_seconds=10))
        status = manager.get_status()
        assert "j" in status
        assert status["j"]["run_count"] == 0
        assert status["j"]["last_run"] is None
        assert status["j"]["running"] is False


class TestRunOnStart:
    @pytest.mark.asyncio()
    async def test_run_on_start_executes_immediately(
        self, manager: CronManager
    ) -> None:
        handler = AsyncMock()
        manager.register(
            JobConfig(
                name="eager",
                handler=handler,
                interval_seconds=9999,
                run_on_start=True,
            )
        )
        await manager.start_all()
        # run_on_start fires as background task — yield to let it execute
        await asyncio.sleep(0.05)
        handler.assert_awaited_once()
        await manager.shutdown()

    @pytest.mark.asyncio()
    async def test_run_on_start_false_skips_immediate(
        self, manager: CronManager
    ) -> None:
        handler = AsyncMock()
        manager.register(
            JobConfig(
                name="lazy",
                handler=handler,
                interval_seconds=9999,
                run_on_start=False,
            )
        )
        await manager.start_all()
        handler.assert_not_awaited()
        await manager.shutdown()


class TestOverlapPrevention:
    @pytest.mark.asyncio()
    async def test_skip_if_still_running(self, manager: CronManager) -> None:
        """A second invocation while the first is blocked should be skipped."""
        call_count = 0
        blocker = asyncio.Event()

        async def slow_handler() -> None:
            nonlocal call_count
            call_count += 1
            await blocker.wait()

        manager.register(
            JobConfig(name="slow", handler=slow_handler, interval_seconds=9999)
        )
        # Manually trigger two overlapping runs
        task1 = asyncio.create_task(manager._run_job("slow"))
        await asyncio.sleep(0.01)  # Let task1 start
        await manager._run_job("slow")  # Should skip (overlap)

        blocker.set()
        await task1

        assert call_count == 1  # Only one actual execution
        assert manager._state["slow"].run_count == 1


class TestRetryWithBackoff:
    @pytest.mark.asyncio()
    async def test_retry_on_failure(self, manager: CronManager) -> None:
        handler = AsyncMock(side_effect=[RuntimeError("boom"), None])
        manager.register(
            JobConfig(
                name="flaky",
                handler=handler,
                interval_seconds=9999,
                max_retries=1,
                retry_backoff_base=0.01,  # Fast backoff for tests
            )
        )
        await manager._run_job("flaky")

        assert handler.await_count == 2
        state = manager._state["flaky"]
        assert state.run_count == 1
        assert state.error_count == 0
        assert state.last_error is None

    @pytest.mark.asyncio()
    async def test_exhausted_retries_records_error(self, manager: CronManager) -> None:
        handler = AsyncMock(side_effect=RuntimeError("persistent"))
        manager.register(
            JobConfig(
                name="broken",
                handler=handler,
                interval_seconds=9999,
                max_retries=2,
                retry_backoff_base=0.01,
            )
        )
        await manager._run_job("broken")

        state = manager._state["broken"]
        assert state.run_count == 0
        assert state.error_count == 1
        assert state.last_error == "persistent"
        assert state.last_run is not None
        assert state.last_duration is not None

    @pytest.mark.asyncio()
    async def test_no_retry_when_max_retries_zero(self, manager: CronManager) -> None:
        handler = AsyncMock(side_effect=RuntimeError("once"))
        manager.register(
            JobConfig(
                name="no_retry",
                handler=handler,
                interval_seconds=9999,
                max_retries=0,
            )
        )
        await manager._run_job("no_retry")

        assert handler.await_count == 1
        assert manager._state["no_retry"].error_count == 1


class TestShutdown:
    @pytest.mark.asyncio()
    async def test_shutdown_cancels_all_tasks(self, manager: CronManager) -> None:
        manager.register(
            JobConfig(name="a", handler=AsyncMock(), interval_seconds=9999)
        )
        manager.register(
            JobConfig(name="b", handler=AsyncMock(), interval_seconds=9999)
        )
        await manager.start_all()
        assert len(manager._tasks) == 2

        await manager.shutdown()
        assert len(manager._tasks) == 0

    @pytest.mark.asyncio()
    async def test_shutdown_idempotent(self, manager: CronManager) -> None:
        await manager.shutdown()  # No jobs — should not raise


class TestGetStatus:
    @pytest.mark.asyncio()
    async def test_status_reflects_successful_run(self, manager: CronManager) -> None:
        manager.register(
            JobConfig(name="ok", handler=AsyncMock(), interval_seconds=9999)
        )
        await manager._run_job("ok")

        status = manager.get_status()["ok"]
        assert status["run_count"] == 1
        assert status["error_count"] == 0
        assert status["last_run"] is not None
        assert status["last_duration"] is not None
        assert status["last_error"] is None
        assert status["running"] is False

    @pytest.mark.asyncio()
    async def test_status_reflects_failed_run(self, manager: CronManager) -> None:
        manager.register(
            JobConfig(
                name="fail",
                handler=AsyncMock(side_effect=RuntimeError("bad")),
                interval_seconds=9999,
                max_retries=0,
            )
        )
        await manager._run_job("fail")

        status = manager.get_status()["fail"]
        assert status["run_count"] == 0
        assert status["error_count"] == 1
        assert status["last_error"] == "bad"
        assert status["running"] is False
