import asyncio
import traceback
import uuid
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone

from loguru import logger
from pydantic import BaseModel

from lnbits.core.models import Payment
from lnbits.settings import settings
from lnbits.utils.electrum import (
    AddressTracker,
    BlockInfo,
    BlockTracker,
    OnchainAddressEvent,
    OnchainTxEvent,
    TransactionTracker,
    scripthash_from_address,
)


class PublicTask(BaseModel):
    """Public model used to expose task information via the API."""

    name: str
    created_at: datetime


class Task:
    """Model used on the backend to keep track of background tasks."""

    coro: Coroutine
    name: str
    created_at: datetime
    task: asyncio.Task
    invoice_queue: asyncio.Queue[Payment] | None = None
    onchain_queue: asyncio.Queue[OnchainAddressEvent] | None = None

    def __init__(
        self,
        coro: Coroutine,
        name: str | None = None,
        invoice_queue: asyncio.Queue | None = None,
        onchain_queue: asyncio.Queue | None = None,
    ) -> None:
        self.coro = coro
        self.name = name or f"task_{uuid.uuid4()}"
        self.created_at = datetime.now(timezone.utc)
        self.task = asyncio.create_task(self.coro, name=self.name)
        self.invoice_queue = invoice_queue
        self.onchain_queue = onchain_queue


class TaskManager:
    """Singleton class to manage background tasks."""

    tasks: list[Task] = []
    invoice_queue: asyncio.Queue[Payment] = asyncio.Queue()
    internal_invoice_queue: asyncio.Queue[Payment] = asyncio.Queue()
    _tracked_addresses: dict[str, int] = {}  # address -> ref count
    _address_tracker: "AddressTracker | None" = None
    _block_tracker: "BlockTracker | None" = None
    _ws_address_queues: dict[str, list[asyncio.Queue[OnchainAddressEvent]]] = {}
    _ws_tx_queues: dict[str, list[asyncio.Queue[OnchainTxEvent]]] = {}
    _ws_block_queues: list[asyncio.Queue[BlockInfo]] = []

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

    def get_public_tasks(self) -> list[PublicTask]:
        """Get a list of public tasks."""
        return [PublicTask(name=t.name, created_at=t.created_at) for t in self.tasks]

    def cancel_task(self, task: Task) -> None:
        """Cancel a running task."""
        self.tasks.remove(task)
        try:
            task.task.cancel()
        except Exception as exc:
            logger.warning(f"error while cancelling task `{task.name}`: {exc!s}")

    def cancel_all_tasks(self) -> None:
        """Cancel all running tasks."""
        for task in list(self.tasks):
            self.cancel_task(task)

    def create_task(
        self,
        coro: Coroutine,
        name: str | None = None,
        invoice_queue: asyncio.Queue | None = None,
        onchain_queue: asyncio.Queue | None = None,
    ) -> Task:
        """Create a task. If a task with the same name exists, it will be cancelled."""
        if name:
            task = self.get_task(name)
            if task:
                self.cancel_task(task)
        task = Task(
            coro=coro,
            name=name,
            invoice_queue=invoice_queue,
            onchain_queue=onchain_queue,
        )
        self.tasks.append(task)
        return task

    def create_permanent_task(
        self,
        func: Callable[[], Coroutine],
        invoice_queue: asyncio.Queue | None = None,
        onchain_queue: asyncio.Queue | None = None,
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
            coro=wrapper(),
            name=name or func.__name__,
            invoice_queue=invoice_queue,
            onchain_queue=onchain_queue,
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

    def register_onchain_listener(
        self,
        func: Callable[[OnchainAddressEvent], Coroutine],
        name: str | None = None,
    ) -> Task:
        """
        Register a callback for onchain address events dispatched by track_address.
        Will call the provided coroutine with an OnchainAddressEvent on each update.
        """
        name = f"{name or uuid.uuid4()}_onchain_listener"
        queue: asyncio.Queue[OnchainAddressEvent] = asyncio.Queue()
        return self.create_permanent_task(
            self._onchain_listener_worker(func, queue),
            name=name,
            onchain_queue=queue,
        )

    def track_address(self, address: str) -> None:
        """Start tracking a Bitcoin address via Electrum (ref-counted)."""
        count = self._tracked_addresses.get(address, 0)
        self._tracked_addresses[address] = count + 1
        if count == 0:
            self._get_address_tracker().add(address)

    def untrack_address(self, address: str) -> None:
        """Decrement ref count; remove from shared tracker when last caller leaves."""
        count = self._tracked_addresses.get(address, 0)
        if count <= 1:
            self._tracked_addresses.pop(address, None)
            if self._address_tracker:
                self._address_tracker.remove(address)
        else:
            self._tracked_addresses[address] = count - 1

    def _get_address_tracker(self) -> "AddressTracker":
        if self._address_tracker is None:
            self._address_tracker = AddressTracker(
                settings.lnbits_blockexplorer_electrum_url
            )
        if not self.get_task("address_tracker"):
            self.create_task(
                self._address_tracker.run(
                    self._dispatch_onchain_event,
                    lambda: settings.lnbits_running,
                ),
                name="address_tracker",
            )
        return self._address_tracker

    def register_ws_address_queue(
        self, address: str, queue: asyncio.Queue[OnchainAddressEvent]
    ) -> None:
        """Register a per-connection queue for a watched address.

        Raises ValueError if the address is invalid.
        """
        scripthash_from_address(address)
        self._ws_address_queues.setdefault(address, []).append(queue)
        self.track_address(address)

    def unregister_ws_address_queue(
        self, address: str, queue: asyncio.Queue[OnchainAddressEvent]
    ) -> None:
        """Deregister a per-connection queue and decrement the address ref count."""
        queues = self._ws_address_queues.get(address, [])
        if queue in queues:
            queues.remove(queue)
        if not queues:
            self._ws_address_queues.pop(address, None)
        self.untrack_address(address)

    def register_ws_tx_queue(
        self, txid: str, queue: asyncio.Queue[OnchainTxEvent]
    ) -> None:
        """Register a per-connection queue for a watched transaction."""
        self._ws_tx_queues.setdefault(txid, []).append(queue)
        if len(self._ws_tx_queues[txid]) == 1:
            self.create_task(
                self._transaction_tracker_dispatch(txid), name=f"ws_tx_{txid}"
            )

    def unregister_ws_tx_queue(
        self, txid: str, queue: asyncio.Queue[OnchainTxEvent]
    ) -> None:
        """Deregister a per-connection queue; cancel tracker when last one leaves."""
        queues = self._ws_tx_queues.get(txid, [])
        if queue in queues:
            queues.remove(queue)
        if not queues:
            self._ws_tx_queues.pop(txid, None)
            task = self.get_task(f"ws_tx_{txid}")
            if task:
                self.cancel_task(task)

    def register_ws_block_queue(self, queue: asyncio.Queue[BlockInfo]) -> None:
        """Register a per-connection queue for new block events."""
        self._ws_block_queues.append(queue)
        if len(self._ws_block_queues) == 1:
            if self._block_tracker is None:
                self._block_tracker = BlockTracker(
                    settings.lnbits_blockexplorer_electrum_url
                )
            self.create_task(
                self._block_tracker.run(
                    self._dispatch_block_event,
                    lambda: bool(self._ws_block_queues) and settings.lnbits_running,
                ),
                name="block_tracker",
            )

    def unregister_ws_block_queue(self, queue: asyncio.Queue[BlockInfo]) -> None:
        """Deregister a per-connection queue; cancel tracker when last one leaves."""
        if queue in self._ws_block_queues:
            self._ws_block_queues.remove(queue)
        if not self._ws_block_queues:
            task = self.get_task("block_tracker")
            if task:
                self.cancel_task(task)

    def track_transaction(
        self,
        txid: str,
        callback: Callable[[OnchainTxEvent], Coroutine],
    ) -> Task:
        """Track a transaction until confirmed, calling callback on each change."""
        return self.create_task(
            self._transaction_tracker(txid, callback),
            name=f"onchain_tx_{txid}",
        )

    async def _heart_beat(self) -> None:
        """A heartbeat that removes done tasks logs the number of tasks."""
        for task in self.tasks:
            state = task.task._state if task.task else "NOT RUNNING"
            if settings.task_heart_beat_verbose:
                logger.debug(
                    f"Task Manager: `{task.name}` state: `{state}` "
                    f"created: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}`"
                )
            if task.task and task.task.done():
                logger.debug(f"Task Manager: task `{task.name}` is done.")
                self.cancel_task(task)
        invoice_listeners = sum(1 for task in self.tasks if task.invoice_queue)
        onchain_listeners = sum(1 for task in self.tasks if task.onchain_queue)
        other_tasks = len(self.tasks) - invoice_listeners - onchain_listeners
        logger.debug(
            f"Task Manager: {other_tasks} tasks, "
            f"{invoice_listeners} invoice listeners, "
            f"{onchain_listeners} onchain listeners."
        )

    async def _catch_everything_and_restart(
        self,
        func: Callable[[], Coroutine],
        restart_interval: int = 5,
    ) -> None:
        """Catches all exceptions from a function and restarts it after 5 seconds."""
        while settings.lnbits_running:
            try:
                return await func()
            except asyncio.CancelledError:
                raise  # because we must pass this up
            except Exception as exc:
                if not settings.lnbits_running:
                    return
                logger.error(f"exception in background task `{func.__name__}`:", exc)
                logger.error(traceback.format_exc())
                logger.info(
                    f"`{func.__name__}` restarts in {restart_interval} seconds."
                )
                await asyncio.sleep(restart_interval)

    def _invoice_listener_worker(
        self, func: Callable[[Payment], Coroutine], queue: asyncio.Queue[Payment]
    ) -> Callable:
        async def wrapper() -> None:
            payment: Payment = await queue.get()
            await func(payment)

        return wrapper

    def _onchain_listener_worker(
        self,
        func: Callable[[OnchainAddressEvent], Coroutine],
        queue: asyncio.Queue[OnchainAddressEvent],
    ) -> Callable:
        async def wrapper() -> None:
            event: OnchainAddressEvent = await queue.get()
            await func(event)

        return wrapper

    def _invoice_dispatcher(self, payment: Payment) -> None:
        """Dispatches a payment to all registered invoice listeners."""
        for task in self.tasks:
            if not task.invoice_queue:
                continue
            logger.debug(f"Enqueing payment to task {task.name}")
            task.invoice_queue.put_nowait(payment)

    async def _dispatch_onchain_event(self, event: OnchainAddressEvent) -> None:
        """Dispatches an onchain address event to listeners and WS queues."""
        for task in self.tasks:
            if task.onchain_queue:
                task.onchain_queue.put_nowait(event)
        for q in list(self._ws_address_queues.get(event.address, [])):
            q.put_nowait(event)

    async def _dispatch_onchain_tx_event(self, event: OnchainTxEvent) -> None:
        """Dispatches a tx event to all WS queues watching that txid."""
        for q in list(self._ws_tx_queues.get(event.txid, [])):
            q.put_nowait(event)

    async def _dispatch_block_event(self, event: BlockInfo) -> None:
        """Dispatches a new block event to all WS queues."""
        for q in list(self._ws_block_queues):
            q.put_nowait(event)

    async def _invoice_listener_consumer(self) -> None:
        payment = await self.invoice_queue.get()
        logger.info(f"got a payment notification {payment.checking_id}")
        self._invoice_dispatcher(payment)

    async def _internal_invoice_listener_consumer(self) -> None:
        payment = await self.internal_invoice_queue.get()
        logger.info(f"got an internal payment notification {payment.checking_id}")
        self._invoice_dispatcher(payment)

    async def _transaction_tracker(
        self, txid: str, callback: Callable[[OnchainTxEvent], Coroutine]
    ) -> None:
        await TransactionTracker(settings.lnbits_blockexplorer_electrum_url).track(
            txid,
            callback,
            lambda: settings.lnbits_running,
        )

    async def _transaction_tracker_dispatch(self, txid: str) -> None:
        await TransactionTracker(settings.lnbits_blockexplorer_electrum_url).track(
            txid,
            self._dispatch_onchain_tx_event,
            lambda: txid in self._ws_tx_queues and settings.lnbits_running,
        )


task_manager = TaskManager()
