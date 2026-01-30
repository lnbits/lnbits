import asyncio
import traceback
import uuid
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone

from loguru import logger
from pydantic import BaseModel

from lnbits.core.models import Payment
from lnbits.settings import settings


class PublicTask(BaseModel):
    """Public model used to expose task information via the API."""

    name: str
    created_at: datetime


class Task:
    """Model used on the backend to keep track of background tasks."""

    coro: Coroutine
    name: str
    created_at: datetime
    _task: asyncio.Task
    invoice_queue: asyncio.Queue[Payment] | None = None

    def __init__(
        self,
        coro: Coroutine,
        name: str | None = None,
        invoice_queue: asyncio.Queue | None = None,
    ) -> None:
        self.coro = coro
        self.name = name or f"task_{uuid.uuid4()}"
        self.created_at = datetime.now(timezone.utc)
        self._task = asyncio.create_task(self.coro, name=self.name)
        self.invoice_queue = invoice_queue


class TaskManager:
    """Singleton class to manage background tasks."""

    tasks: list[Task] = []
    invoice_queue: asyncio.Queue[Payment] = asyncio.Queue()
    internal_invoice_queue: asyncio.Queue[Payment] = asyncio.Queue()

    def init(self) -> None:
        self.create_permanent_task(
            func=self._heart_beat,
            interval=settings.task_heart_beat_interval,
        )
        self.create_permanent_task(self._invoice_listener_consumer)
        self.create_permanent_task(self._internal_invoice_listener_consumer)

    def get_task(self, name: str) -> Task | None:
        """Get a running task by name."""
        for task in self.tasks:
            if task.name == name:
                return task
        return None

    def cancel_task(self, task: Task) -> None:
        """Cancel a running task."""
        self.tasks.remove(task)
        try:
            task._task.cancel()
        except Exception as exc:
            logger.warning(f"error while cancelling task `{task.name}`: {exc!s}")

    def cancel_all_tasks(self) -> None:
        """Cancel all running tasks."""
        for task in self.tasks:
            self.cancel_task(task)

    def create_task(
        self,
        coro: Coroutine,
        name: str | None = None,
        invoice_queue: asyncio.Queue | None = None,
    ) -> Task:
        """Create a task. If a task with the same name exists, it will be cancelled."""
        if name:
            task = self.get_task(name)
            if task:
                self.cancel_task(task)
        task = Task(coro=coro, name=name, invoice_queue=invoice_queue)
        self.tasks.append(task)
        return task

    def create_permanent_task(
        self,
        func: Callable[[], Coroutine],
        invoice_queue: asyncio.Queue | None = None,
        name: str | None = None,
        interval: int = 0,
    ) -> Task:
        """Create a task that runs forever and restarts on failure."""

        async def wrapper():
            while settings.lnbits_running:
                await self._catch_everything_and_restart(func)
                if interval > 0:
                    await asyncio.sleep(interval)

        return self.create_task(
            coro=wrapper(), name=name or func.__name__, invoice_queue=invoice_queue
        )

    def register_invoice_listener(
        self,
        func: Callable[[Payment], Coroutine],
        name: str | None = None,
    ) -> Task:
        """
        A method intended for extensions to call when they want to be notified about
        incoming payments. Will call provided Coroutine with the updated payment.
        """
        name = f"{name or uuid.uuid4()}_invoice_listener"
        queue: asyncio.Queue[Payment] = asyncio.Queue()
        return self.create_permanent_task(
            self._invoice_listener_worker(func, queue),
            name=name,
            invoice_queue=queue,
        )

    async def _heart_beat(self) -> None:
        """A heartbeat that removes done tasks logs the number of tasks."""
        for task in self.tasks:
            state = task._task._state if task._task else "NOT RUNNING"
            if settings.task_heart_beat_verbose:
                logger.debug(
                    f"Task Manager: `{task.name}` state: `{state}` "
                    f"created: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}`"
                )
            if task._task and task._task.done():
                logger.debug(f"Task Manager: task `{task.name}` is done.")
                self.cancel_task(task)
        listeners_count = sum(1 for task in self.tasks if task.invoice_queue)
        logger.debug(
            f"Task Manager: {len(self.tasks) - listeners_count} tasks "
            f"and {listeners_count} invoice listeners."
        )

    async def _catch_everything_and_restart(
        self,
        func: Callable[[], Coroutine],
        restart_interval: int = 5,
    ):
        """Catches all exceptions from a function and restarts it after 5 seconds."""
        try:
            return await func()
        except asyncio.CancelledError:
            raise  # because we must pass this up
        except Exception as exc:
            logger.error(f"exception in background task `{func.__name__}`:", exc)
            logger.error(traceback.format_exc())
            logger.info(f"`{func.__name__}` restarts in {restart_interval} seconds.")
            await asyncio.sleep(restart_interval)
            return await self._catch_everything_and_restart(func, restart_interval)

    def _invoice_listener_worker(
        self, func: Callable[[Payment], Coroutine], queue: asyncio.Queue[Payment]
    ) -> Callable:
        async def wrapper() -> None:
            payment: Payment = await queue.get()
            await func(payment)

        return wrapper

    def _invoice_dispatcher(self, payment: Payment) -> None:
        """Dispatches a payment to all registered invoice listeners."""
        for task in self.tasks:
            if not task.invoice_queue:
                continue
            logger.debug(f"Enqueing payment to task {task.name}")
            task.invoice_queue.put_nowait(payment)

    async def _invoice_listener_consumer(self) -> None:
        payment = await self.invoice_queue.get()
        logger.info(f"got a payment notification {payment.checking_id}")
        self._invoice_dispatcher(payment)

    async def _internal_invoice_listener_consumer(self) -> None:
        payment = await self.internal_invoice_queue.get()
        logger.info(f"got an internal payment notification {payment.checking_id}")
        self._invoice_dispatcher(payment)


task_manager = TaskManager()
