import asyncio
import uuid
from collections.abc import Callable, Coroutine

from loguru import logger

from lnbits.core.models import Payment
from lnbits.task_manager import task_manager


# DEPRECATED: use task_manager.create_task instead.
def create_task(coro: Coroutine) -> asyncio.Task:
    logger.warning("`create_task` is deprecated, use task_manager.create_task instead.")
    return task_manager.create_task(coro)._task


# DEPRECATED: use task_manager.create_task with `name` kwarg.
def create_unique_task(name: str, coro: Coroutine) -> asyncio.Task:
    logger.warning("`create_unique_task` is deprecated, use task_manager.create_task.")
    return task_manager.create_task(coro, name=name)._task


# DEPRECATED: use task_manager.create_permanent_task instead.
def create_permanent_task(func: Callable[[], Coroutine]) -> asyncio.Task:
    logger.warning(
        "`create_permanent_task` is deprecated, "
        "use task_manager.create_permanent_task instead."
    )
    return task_manager.create_permanent_task(func)._task


# DEPRECATED: use task_manager.create_permanent_task with `name` argument instead.
def create_permanent_unique_task(
    name: str, coro: Callable[[], Coroutine]
) -> asyncio.Task:
    logger.warning(
        "`create_permanent_unique_task` is deprecated, "
        "use task_manager.create_permanent_task."
    )
    return create_unique_task(name, catch_everything_and_restart(coro, name))


# DEPRECATED don't use this, use task_manager.create_permanent_task instead.
async def catch_everything_and_restart(
    func: Callable[[], Coroutine],
    name: str = "unnamed",
) -> Coroutine:
    logger.warning(
        "`catch_everything_and_restart` is deprecated, it is internal to task_manager "
        "and should not be needed outside. Use task_manager.create_permanent_task."
    )
    _ = name
    return await task_manager._catch_everything_and_restart(func)


def register_invoice_listener(send_chan: asyncio.Queue, name: str | None = None):
    """
    DEPRECATED: use task_manager.register_invoice_listener instead,
    which also allows to pass a callback instead of a queue.
    This method will still work but it is not recommended for new code.
    """
    logger.warning(
        "register_invoice_listener is deprecated use "
        "task_manager.register_invoice_listener instead."
    )
    name = f"forward_{name or str(uuid.uuid4())[:8]}"

    # here we just forwarding the payments to the provided queue
    async def forward_queue(payment: Payment):
        send_chan.put_nowait(payment)

    task_manager.register_invoice_listener(forward_queue, name=name)
