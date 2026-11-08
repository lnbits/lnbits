import asyncio

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.task_manager import task_manager


@pytest.mark.anyio
async def test_periodic_task_waits_its_interval_after_a_failure(
    mocker: MockerFixture,
):
    real_sleep = asyncio.sleep
    sleeps: list[float] = []

    async def failing_check() -> None:
        raise RuntimeError("funding source unavailable")

    async def fake_sleep(delay: float, *args, **kwargs):
        # only intercept the sleeps of the task under test
        if asyncio.current_task() is not task.task:
            return await real_sleep(delay, *args, **kwargs)
        sleeps.append(delay)
        if len(sleeps) == 2:
            raise asyncio.CancelledError()

    mocker.patch("lnbits.task_manager.logger")
    mocker.patch("lnbits.task_manager.asyncio.sleep", side_effect=fake_sleep)

    task = task_manager.create_permanent_task(failing_check, interval=60)
    with pytest.raises(asyncio.CancelledError):
        await task.task
    task_manager.cancel_task(task)

    assert sleeps == [60, 60]
