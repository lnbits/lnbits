import asyncio
import uuid
from collections.abc import Callable, Coroutine

from loguru import logger

from lnbits.core.models import Payment
from lnbits.settings import settings
from lnbits.task_manager import task_manager


# DEPRECATED: use task_manager.create_task instead.
def create_task(coro: Coroutine) -> asyncio.Task:
    return task_manager.create_task(coro)._task


# DEPRECATED: use task_manager.create_task with `name` kwarg.
def create_unique_task(name: str, coro: Coroutine) -> asyncio.Task:
    return task_manager.create_task(coro, name=name)._task


# DEPRECATED: use task_manager.create_permanent_task instead.
def create_permanent_task(func: Callable[[], Coroutine]) -> asyncio.Task:
    return task_manager.create_permanent_task(func)._task


# DEPRECATED: use task_manager.create_permanent_task with `name` argument instead.
def create_permanent_unique_task(
    name: str, coro: Callable[[], Coroutine]
) -> asyncio.Task:
    return create_unique_task(name, catch_everything_and_restart(coro, name))


# DEPRECATED don't use this, use task_manager.create_permanent_task instead.
async def catch_everything_and_restart(
    func: Callable[[], Coroutine],
    name: str = "unnamed",
) -> Coroutine:
    _ = name
    return await task_manager._catch_everything_and_restart(func)


def register_invoice_listener(send_chan: asyncio.Queue, name: str | None = None):
    """
    DEPRECATED: use task_manager.register_invoice_listener instead,
    which also allows to pass a callback instead of a queue.
    This method will still work but it is not recommended for new code.
    """
    logger.debug(
        "register_invoice_listener is deprecated use "
        "task_manager.register_invoice_listener instead."
    )
    name = f"forward_{name or str(uuid.uuid4())[:8]}"

    # here we just forwarding the payments to the provided queue
    async def forward_queue(payment: Payment):
        send_chan.put_nowait(payment)

    task_manager.register_invoice_listener(forward_queue, name=name)


# DEPRECATED use task_manager.register_invoice_listener(coro, name="myext")
def wait_for_paid_invoices(
    invoice_listener_name: str,
    func: Callable[[Payment], Coroutine],
) -> Callable[[], Coroutine]:
    logger.debug(
        "wait_for_paid_invoices is deprecated use "
        "task_manager.register_invoice_listener instead."
    )

    async def wrapper() -> None:
        invoice_queue: asyncio.Queue = asyncio.Queue()
        register_invoice_listener(invoice_queue, invoice_listener_name)
        while settings.lnbits_running:
            payment = await invoice_queue.get()
            await func(payment)

    return wrapper
