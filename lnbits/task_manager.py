import asyncio
import traceback
import uuid
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from pydantic import BaseModel

from lnbits.core.models import Payment
from lnbits.settings import settings


class PublicTask(BaseModel):
    """Public model used to expose task information via the API."""

    name: str
    created_at: datetime


class OnchainAddressEvent(BaseModel):
    address: str
    confirmed: int  # satoshis
    unconfirmed: int  # satoshis
    txids: list[str]


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
    _tracked_addresses: dict[str, str] = {}  # address -> task_name

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
        task = Task(coro=coro, name=name, invoice_queue=invoice_queue, onchain_queue=onchain_queue)
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
        """Start tracking a Bitcoin address via Electrum. Dispatches OnchainAddressEvents."""
        if address in self._tracked_addresses:
            return
        task_name = f"onchain_address_{address}"
        self._tracked_addresses[address] = task_name
        self.create_task(self._address_tracker(address), name=task_name)

    def untrack_address(self, address: str) -> None:
        """Stop tracking a Bitcoin address."""
        task_name = self._tracked_addresses.pop(address, None)
        if task_name:
            task = self.get_task(task_name)
            if task:
                self.cancel_task(task)

    def track_transaction(
        self,
        txid: str,
        callback: Callable[[str, int], Coroutine],
    ) -> Task:
        """
        Poll until a transaction is confirmed, then call callback(txid, block_height).
        The task cancels itself after the callback fires.
        """
        task_name = f"onchain_tx_{txid}"
        return self.create_task(self._transaction_tracker(txid, callback), name=task_name)

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

    def _dispatch_onchain_event(self, event: OnchainAddressEvent) -> None:
        """Dispatches an onchain address event to all registered onchain listeners."""
        for task in self.tasks:
            if not task.onchain_queue:
                continue
            task.onchain_queue.put_nowait(event)

    async def _invoice_listener_consumer(self) -> None:
        payment = await self.invoice_queue.get()
        logger.info(f"got a payment notification {payment.checking_id}")
        self._invoice_dispatcher(payment)

    async def _internal_invoice_listener_consumer(self) -> None:
        payment = await self.internal_invoice_queue.get()
        logger.info(f"got an internal payment notification {payment.checking_id}")
        self._invoice_dispatcher(payment)

    async def _address_tracker(self, address: str) -> None:
        """Track an address via Electrum subscription; dispatches OnchainAddressEvents."""
        from lnbits.utils.electrum import ElectrumClient, ElectrumError, scripthash_from_address

        electrum_url = settings.lnbits_blockexplorer_electrum_url
        scripthash = scripthash_from_address(address)

        while address in self._tracked_addresses and settings.lnbits_running:
            try:
                async with ElectrumClient(electrum_url) as client:
                    await self._fetch_and_dispatch_address(client, address, scripthash)

                    async def on_status_change(params: list[Any]) -> None:
                        if params and params[0] == scripthash:
                            await self._fetch_and_dispatch_address(client, address, scripthash)

                    await client.subscribe_scripthash(scripthash, on_status_change)

                    while address in self._tracked_addresses and settings.lnbits_running:
                        await asyncio.sleep(30)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not settings.lnbits_running:
                    return
                logger.warning(f"Address tracker {address}: {exc!s}, retrying in 5s")
                await asyncio.sleep(5)

    async def _fetch_and_dispatch_address(
        self, client: Any, address: str, scripthash: str
    ) -> None:
        """Fetch balance + history for a scripthash and dispatch an OnchainAddressEvent."""
        from lnbits.utils.electrum import ElectrumError

        balance = await client.get_balance(scripthash)
        txids: list[str] = []
        try:
            history = await client.get_history(scripthash)
            txids = [e.tx_hash for e in history]
        except ElectrumError:
            pass
        try:
            mempool = await client.get_mempool(scripthash)
            for e in mempool:
                if e.tx_hash not in txids:
                    txids.append(e.tx_hash)
        except ElectrumError:
            pass
        self._dispatch_onchain_event(
            OnchainAddressEvent(
                address=address,
                confirmed=balance.confirmed,
                unconfirmed=balance.unconfirmed,
                txids=txids,
            )
        )

    async def _transaction_tracker(
        self, txid: str, callback: Callable[[str, int], Coroutine]
    ) -> None:
        """Poll Electrum until txid is confirmed, then fire callback(txid, height)."""
        from lnbits.utils.electrum import ElectrumClient

        electrum_url = settings.lnbits_blockexplorer_electrum_url
        while settings.lnbits_running:
            try:
                async with ElectrumClient(electrum_url) as client:
                    tx = await client.get_transaction(txid, verbose=True)
                    if isinstance(tx, dict):
                        height = tx.get("blockheight") or tx.get("block_height", 0)
                        if height and height > 0:
                            await callback(txid, height)
                            return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not settings.lnbits_running:
                    return
                logger.warning(f"Tx tracker {txid[:8]}: {exc!s}")
            await asyncio.sleep(60)


task_manager = TaskManager()
