import asyncio
import traceback
import uuid
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import TypeVar

from fastapi import WebSocket
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
    onchain_address_queue: asyncio.Queue[OnchainAddressEvent] | None = None
    onchain_tx_queue: asyncio.Queue[OnchainTxEvent] | None = None
    block_queue: asyncio.Queue[BlockInfo] | None = None

    def __init__(
        self,
        coro: Coroutine,
        name: str | None = None,
        invoice_queue: asyncio.Queue | None = None,
        onchain_address_queue: asyncio.Queue | None = None,
        onchain_tx_queue: asyncio.Queue | None = None,
        block_queue: asyncio.Queue | None = None,
    ) -> None:
        self.coro = coro
        self.name = name or f"task_{uuid.uuid4()}"
        self.created_at = datetime.now(timezone.utc)
        self.task = asyncio.create_task(self.coro, name=self.name)
        self.invoice_queue = invoice_queue
        self.onchain_address_queue = onchain_address_queue
        self.onchain_tx_queue = onchain_tx_queue
        self.block_queue = block_queue


class TaskManager:
    """Singleton class to manage background tasks."""

    ONCHAIN_ADDRESS_LISTENER_SUFFIX = "_onchain_address_listener"

    tasks: list[Task] = []
    invoice_queue: asyncio.Queue[Payment] = asyncio.Queue()
    internal_invoice_queue: asyncio.Queue[Payment] = asyncio.Queue()
    _address_tracker: "AddressTracker | None" = None
    _block_tracker: "BlockTracker | None" = None
    _tx_trackers: dict[str, "TransactionTracker"] = {}
    _tracked_addresses_by_listener: dict[str, set[str]] = {}

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
        onchain_address_queue: asyncio.Queue | None = None,
        onchain_tx_queue: asyncio.Queue | None = None,
        block_queue: asyncio.Queue | None = None,
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
            onchain_address_queue=onchain_address_queue,
            onchain_tx_queue=onchain_tx_queue,
            block_queue=block_queue,
        )
        self.tasks.append(task)
        return task

    def create_permanent_task(
        self,
        func: Callable[[], Coroutine],
        invoice_queue: asyncio.Queue | None = None,
        onchain_address_queue: asyncio.Queue | None = None,
        onchain_tx_queue: asyncio.Queue | None = None,
        block_queue: asyncio.Queue | None = None,
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
            onchain_address_queue=onchain_address_queue,
            onchain_tx_queue=onchain_tx_queue,
            block_queue=block_queue,
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
        Register a callback for onchain address events. Only dispatches events
        for addresses tracked under the same `name` via track_address, e.g. an
        extension registering as "ext_satspay" only sees events for addresses
        it tracked with that same name. Defaults to the shared "core" listener
        if no name is given.
        """
        name = name or "core"
        queue: asyncio.Queue[OnchainAddressEvent] = asyncio.Queue()
        return self.create_permanent_task(
            self._onchain_address_listener_worker(func, queue),
            name=f"{name}{self.ONCHAIN_ADDRESS_LISTENER_SUFFIX}",
            onchain_address_queue=queue,
        )

    def register_onchain_tx_listener(
        self,
        func: Callable[[OnchainTxEvent], Coroutine],
        name: str | None = None,
    ) -> Task:
        """
        Register a callback for onchain transaction events dispatched for any
        transaction currently tracked via register_ws_tx_queue.
        Will call the provided coroutine with an OnchainTxEvent on each update.
        """
        name = f"{name or uuid.uuid4()}_onchain_tx_listener"
        queue: asyncio.Queue[OnchainTxEvent] = asyncio.Queue()
        return self.create_permanent_task(
            self._onchain_tx_listener_worker(func, queue),
            name=name,
            onchain_tx_queue=queue,
        )

    def register_block_listener(
        self,
        func: Callable[[BlockInfo], Coroutine],
        name: str | None = None,
    ) -> Task:
        """
        Register a callback for new block events dispatched while the shared
        block tracker is running (i.e. while a websocket or other consumer has
        requested block updates via register_ws_block_queue).
        Will call the provided coroutine with a BlockInfo on each new block.
        """
        name = f"{name or uuid.uuid4()}_block_listener"
        queue: asyncio.Queue[BlockInfo] = asyncio.Queue()
        return self.create_permanent_task(
            self._block_listener_worker(func, queue),
            name=name,
            block_queue=queue,
        )

    def track_address(self, address: str, name: str) -> None:
        """Start tracking a Bitcoin address via Electrum (ref-counted).

        `name` identifies the listener (see register_onchain_listener) that
        should receive events for this address.
        """
        self._get_address_tracker().add(address)
        self._tracked_addresses_by_listener.setdefault(name, set()).add(address)

    def untrack_address(self, address: str, name: str) -> None:
        """Decrement ref count; remove from shared tracker when last caller leaves."""
        if self._address_tracker:
            self._address_tracker.remove(address)
        tracked = self._tracked_addresses_by_listener.get(name)
        if tracked:
            tracked.discard(address)
            if not tracked:
                self._tracked_addresses_by_listener.pop(name, None)

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
        self._get_address_tracker().register_queue(address, queue)

    def unregister_ws_address_queue(
        self, address: str, queue: asyncio.Queue[OnchainAddressEvent]
    ) -> None:
        """Deregister a per-connection queue and decrement the address ref count."""
        if self._address_tracker:
            self._address_tracker.unregister_queue(address, queue)

    def register_ws_tx_queue(
        self, txid: str, queue: asyncio.Queue[OnchainTxEvent]
    ) -> None:
        """Register a per-connection queue for a watched transaction."""
        self._get_tx_tracker(txid).register_queue(queue)

    def unregister_ws_tx_queue(
        self, txid: str, queue: asyncio.Queue[OnchainTxEvent]
    ) -> None:
        """Deregister a per-connection queue; cancel tracker when last one leaves."""
        tracker = self._tx_trackers.get(txid)
        if not tracker:
            return
        tracker.unregister_queue(queue)
        if not tracker.has_queues():
            self._tx_trackers.pop(txid, None)
            task = self.get_task(f"ws_tx_{txid}")
            if task:
                self.cancel_task(task)

    def _get_tx_tracker(self, txid: str) -> "TransactionTracker":
        tracker = self._tx_trackers.get(txid)
        if tracker is None:
            tracker = TransactionTracker(settings.lnbits_blockexplorer_electrum_url)
            self._tx_trackers[txid] = tracker
        if not self.get_task(f"ws_tx_{txid}"):
            self.create_task(
                self._transaction_tracker_dispatch(txid, tracker),
                name=f"ws_tx_{txid}",
            )
        return tracker

    def register_ws_block_queue(self, queue: asyncio.Queue[BlockInfo]) -> None:
        """Register a per-connection queue for new block events."""
        if self._block_tracker is None:
            self._block_tracker = BlockTracker(
                settings.lnbits_blockexplorer_electrum_url
            )
        tracker = self._block_tracker
        was_empty = not tracker.has_queues()
        tracker.register_queue(queue)
        if was_empty:
            self.create_task(
                tracker.run(
                    self._dispatch_block_event,
                    lambda: tracker.has_queues() and settings.lnbits_running,
                ),
                name="block_tracker",
            )

    def unregister_ws_block_queue(self, queue: asyncio.Queue[BlockInfo]) -> None:
        """Deregister a per-connection queue; cancel tracker when last one leaves."""
        if not self._block_tracker:
            return
        self._block_tracker.unregister_queue(queue)
        if not self._block_tracker.has_queues():
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
        onchain_listeners = sum(
            1
            for task in self.tasks
            if task.onchain_address_queue or task.onchain_tx_queue or task.block_queue
        )
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

    def _onchain_address_listener_worker(
        self,
        func: Callable[[OnchainAddressEvent], Coroutine],
        queue: asyncio.Queue[OnchainAddressEvent],
    ) -> Callable:
        async def wrapper() -> None:
            event: OnchainAddressEvent = await queue.get()
            await func(event)

        return wrapper

    def _onchain_tx_listener_worker(
        self,
        func: Callable[[OnchainTxEvent], Coroutine],
        queue: asyncio.Queue[OnchainTxEvent],
    ) -> Callable:
        async def wrapper() -> None:
            event: OnchainTxEvent = await queue.get()
            await func(event)

        return wrapper

    def _block_listener_worker(
        self,
        func: Callable[[BlockInfo], Coroutine],
        queue: asyncio.Queue[BlockInfo],
    ) -> Callable:
        async def wrapper() -> None:
            event: BlockInfo = await queue.get()
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
        """Dispatches an onchain address event to listeners tracking that
        address under their own name (see track_address).

        Per-address WS queue fan-out is handled by AddressTracker itself.
        """
        for task in self.tasks:
            if not task.onchain_address_queue:
                continue
            if not task.name.endswith(self.ONCHAIN_ADDRESS_LISTENER_SUFFIX):
                continue
            name = task.name[: -len(self.ONCHAIN_ADDRESS_LISTENER_SUFFIX)]
            if event.address in self._tracked_addresses_by_listener.get(name, ()):
                task.onchain_address_queue.put_nowait(event)

    async def _dispatch_onchain_tx_event(self, event: OnchainTxEvent) -> None:
        """Dispatches an onchain tx event to registered listeners.

        Per-tx WS queue fan-out is handled by TransactionTracker itself.
        """
        for task in self.tasks:
            if task.onchain_tx_queue:
                task.onchain_tx_queue.put_nowait(event)

    async def _dispatch_block_event(self, event: BlockInfo) -> None:
        """Dispatches a new block event to registered listeners.

        Per-connection WS queue fan-out is handled by BlockTracker itself.
        """
        for task in self.tasks:
            if task.block_queue:
                task.block_queue.put_nowait(event)

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

    async def _transaction_tracker_dispatch(
        self, txid: str, tracker: "TransactionTracker"
    ) -> None:
        await tracker.track(
            txid,
            self._dispatch_onchain_tx_event,
            lambda: tracker.has_queues() and settings.lnbits_running,
        )


T = TypeVar("T", bound=BaseModel)


async def relay_ws_queue(
    websocket: WebSocket,
    queue: "asyncio.Queue[T]",
    serialize: Callable[[T], BaseModel] = lambda e: e,
    stop_after: Callable[[T], bool] = lambda _: False,
) -> None:
    """
    Pumps events from `queue` to `websocket` as JSON until the client
    disconnects, sending fails, or `stop_after` returns True for an event.
    Shared by the blockexplorer address/tx/block websocket endpoints.
    """
    try:
        while True:
            recv_task = asyncio.create_task(websocket.receive())
            event_task = asyncio.create_task(queue.get())
            done, pending = await asyncio.wait(
                [recv_task, event_task], return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
            disconnect = recv_task in done and (
                recv_task.result().get("type") == "websocket.disconnect"
            )
            if disconnect:
                break
            if event_task in done:
                event = event_task.result()
                try:
                    await websocket.send_json(serialize(event).dict())
                except Exception as exc:
                    logger.debug(f"ws relay send error: {exc}")
                    break
                if stop_after(event):
                    break
    except Exception as exc:
        logger.debug(f"ws relay error: {exc}")


task_manager = TaskManager()
