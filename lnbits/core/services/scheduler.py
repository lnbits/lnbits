import asyncio
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from loguru import logger

from lnbits.core.crud import scheduler as crud
from lnbits.core.crud.extensions import get_installed_extension, get_user_extension
from lnbits.core.crud.users import get_account
from lnbits.core.models.scheduler import ScheduleConfig, ScheduledJob, next_run_at
from lnbits.settings import settings

SCHEDULER_USER_PERMISSION = "scheduler.user"
SCHEDULER_EXTENSION_PERMISSION = "scheduler.extension"
ScheduleHandler = Callable[[ScheduledJob], Awaitable[None]]


async def check_schedule_access(namespace: str, user_id: str | None) -> None:
    """Check current grants, including on executions after the user logs out."""
    if user_id:
        account = await get_account(user_id)
        if not account or not account.activated:
            raise PermissionError("Schedule owner is not active.")
    if namespace == "core":
        return
    if (
        not namespace.startswith("extension:")
        or settings.lnbits_extensions_deactivate_all
    ):
        raise PermissionError("Extension scheduling is unavailable.")
    extension_id = namespace.removeprefix("extension:")
    extension = await get_installed_extension(extension_id)
    if not extension or not extension.active:
        raise PermissionError("Scheduled extension is not active.")
    permission = (
        SCHEDULER_USER_PERMISSION if user_id else SCHEDULER_EXTENSION_PERMISSION
    )
    # Python extensions are trusted application code; WASM grants are host-enforced.
    if extension.is_wasm and permission not in {
        item.id for item in extension.permissions
    }:
        raise PermissionError("Extension scheduling permission has been revoked.")
    if user_id:
        user_extension = await get_user_extension(user_id, extension_id)
        if not user_extension or not user_extension.active:
            raise PermissionError("Scheduled extension is not active for this user.")


class Scheduler:
    """Persistent cron jobs dispatched to explicitly registered async callbacks.

    Registration and direct access are trusted Python APIs. WASM callers use the
    scoped host API, which never accepts a namespace or user ID from the guest.
    """

    def __init__(self, *, concurrency: int = 4, lease_seconds: int = 60):
        if concurrency < 1 or lease_seconds < 3:
            raise ValueError("Invalid scheduler concurrency or lease duration.")
        self.concurrency = concurrency
        self.lease_seconds = lease_seconds
        self.handlers: dict[tuple[str, str], ScheduleHandler] = {}
        self.running: dict[str, tuple[ScheduledJob, asyncio.Task]] = {}
        self.stopping = False

    def register(self, namespace: str, handler: str, callback: ScheduleHandler) -> None:
        if namespace != "core" and not namespace.startswith("extension:"):
            raise ValueError("Use the core or extension:<id> namespace.")
        self.handlers[(namespace, handler)] = callback

    def unregister(self, namespace: str) -> None:
        self.handlers = {
            key: callback
            for key, callback in self.handlers.items()
            if key[0] != namespace
        }
        for job, task in self.running.values():
            if job.namespace == namespace:
                task.cancel()

    async def stop_namespace(self, namespace: str, timeout: float = 5.0) -> None:
        """Cancel this namespace's jobs and bound the wait for their cleanup."""
        self.unregister(namespace)
        tasks = [
            task for job, task in self.running.values() if job.namespace == namespace
        ]
        if not tasks:
            return
        # Keep unfinished jobs tracked; timing out must not cancel their cleanup.
        done, pending = await asyncio.wait(tasks, timeout=timeout)
        for task in done:
            if not task.cancelled():
                task.exception()
        if pending:
            logger.warning(
                "Scheduler stop for {} exceeded {} seconds; {} jobs remain unfinished.",
                namespace,
                timeout,
                len(pending),
            )

    async def save(
        self, namespace: str, config: ScheduleConfig, *, user_id: str | None = None
    ) -> ScheduledJob:
        await check_schedule_access(namespace, user_id)
        if (namespace, config.handler) not in self.handlers:
            raise ValueError("Schedule handler is not registered.")
        now = int(time.time())
        next_run = next_run_at(config.cron_expression, config.timezone, now)
        if next_run is None:
            raise ValueError("Cron expression has no occurrence within eight years.")
        return await crud.save_scheduled_job(
            ScheduledJob(
                **config.dict(),
                namespace=namespace,
                user_id=user_id,
                next_run_at=next_run,
            )
        )

    async def list(
        self,
        namespace: str,
        *,
        user_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ScheduledJob]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid schedule pagination.")
        return await crud.list_scheduled_jobs(
            namespace, user_id, limit=limit, offset=offset
        )

    async def delete(
        self, namespace: str, job_id: str, *, user_id: str | None = None
    ) -> bool:
        job = await crud.get_scheduled_job(job_id)
        if not job or job.namespace != namespace or job.user_id != user_id:
            return False
        if job.lease_token and job.lease_until > int(time.time()):
            raise ValueError(
                "Job is running. Pause it and wait for it to stop before deleting."
            )
        return await crud.delete_scheduled_job(
            job_id, namespace, user_id, int(time.time())
        )

    async def tick(self) -> None:
        for job_id, (_, task) in list(self.running.items()):
            if task.done():
                # Workers handle callback errors, but database failures may escape.
                if not task.cancelled() and task.exception():
                    logger.warning("Scheduled job {} failed to finalize.", job_id)
                self.running.pop(job_id)
        available = self.concurrency - len(self.running)
        if available <= 0 or self.stopping:
            return
        now = int(time.time())
        for candidate in await crud.get_due_scheduled_jobs(now, available):
            if self.stopping or candidate.id in self.running:
                continue
            job = await crud.claim_scheduled_job(
                candidate.id, uuid4().hex, now, now + self.lease_seconds
            )
            if job and not self.stopping:
                self.running[job.id] = (
                    job,
                    asyncio.create_task(self._run_job(job), name=f"schedule_{job.id}"),
                )

    async def run(self) -> None:
        self.stopping = False
        try:
            while settings.lnbits_running and not self.stopping:
                await self.tick()
                await asyncio.sleep(1)
        finally:
            await self.stop()

    async def stop(self) -> None:
        tasks = [task for _, task in self.running.values()]
        if not self.stopping:
            self.stopping = True
            for task in tasks:
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.running.clear()

    async def _execute(self, job: ScheduledJob) -> None:
        await check_schedule_access(job.namespace, job.user_id)
        current = await crud.get_scheduled_job(job.id)
        if not current or not current.enabled or current.lease_token != job.lease_token:
            return
        callback = self.handlers.get((current.namespace, current.handler))
        if callback:
            await callback(current)

    async def _heartbeat(self, job: ScheduledJob) -> None:
        assert job.lease_token
        while True:
            await asyncio.sleep(self.lease_seconds / 3)
            await check_schedule_access(job.namespace, job.user_id)
            now = int(time.time())
            if not await crud.renew_scheduled_job(
                job.id, job.lease_token, now, now + self.lease_seconds
            ):
                raise RuntimeError("Schedule claim lost or job paused.")

    async def _run_job(self, job: ScheduledJob) -> None:
        work = asyncio.create_task(self._execute(job))
        heartbeat = asyncio.create_task(self._heartbeat(job))
        cancelled = False
        try:
            done, _ = await asyncio.wait(
                (work, heartbeat), return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                task.result()
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception:
            logger.warning(
                "Scheduled job {} failed; next attempt follows its cron schedule.",
                job.id,
            )
        finally:
            work.cancel()
            heartbeat.cancel()
            await asyncio.gather(work, heartbeat, return_exceptions=True)
            # On shutdown leave the durable lease to expire, so interrupted jobs
            # are recovered once on restart. Successful/failed jobs skip overlap.
            if not cancelled:
                following = next_run_at(
                    job.cron_expression, job.timezone, int(time.time())
                )
                await crud.finish_scheduled_job(job, following)


scheduler = Scheduler()
_stop_tasks: set[asyncio.Task[None]] = set()


async def stop_scheduler_safely(timeout: float = 5.0) -> None:
    """Bound the shutdown wait while allowing in-flight cleanup to finish.

    Stop failures are logged; cancellation of this caller still propagates.
    The deadline requires a responsive event loop and cannot kill native threads.
    """

    async def stop() -> None:
        try:
            await scheduler.stop()
        except asyncio.CancelledError:
            logger.warning("Scheduler shutdown was cancelled.")
        except Exception:
            logger.warning("Scheduler shutdown failed.")

    task = asyncio.create_task(stop(), name="scheduler_shutdown")
    # Retain cleanup after the caller returns, and consume failures inside stop().
    _stop_tasks.add(task)
    task.add_done_callback(_stop_tasks.discard)
    # wait() does not cancel or wait for uncooperative cleanup on timeout.
    _, pending = await asyncio.wait({task}, timeout=timeout)
    if pending:
        unfinished = sum(not task.done() for _, task in scheduler.running.values())
        logger.warning(
            "Scheduler shutdown exceeded {} seconds; {} jobs remain unfinished.",
            timeout,
            unfinished,
        )
