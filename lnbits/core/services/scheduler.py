import asyncio
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from loguru import logger

from lnbits.core.crud.extensions import get_installed_extension, get_user_extension
from lnbits.core.crud.scheduler import (
    claim_scheduled_job,
    create_scheduled_job_run,
    delete_excess_scheduled_job_runs,
    delete_expired_scheduled_job_runs,
    delete_scheduled_job,
    finish_scheduled_job,
    finish_scheduled_job_run,
    get_due_scheduled_jobs,
    get_scheduled_job,
    get_scheduled_jobs_count,
    get_scheduled_jobs_paginated,
    interrupt_expired_scheduled_job_runs,
    renew_scheduled_job,
    save_scheduled_job,
)
from lnbits.core.crud.users import get_account
from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.models.scheduler import (
    ScheduleConfig,
    ScheduledJob,
    ScheduledJobRun,
    ScheduledJobRunStatus,
    SchedulePolicy,
    UserSchedulePolicy,
)
from lnbits.db import Page
from lnbits.settings import settings
from lnbits.utils.cron import next_run_at
from lnbits.utils.error import safe_error_message

SCHEDULER_USER_PERMISSION = "scheduler.user"
SCHEDULER_EXTENSION_PERMISSION = "scheduler.extension"
ScheduleHandler = Callable[[ScheduledJob], Awaitable[None]]


async def maintain_scheduled_job_runs(now: float) -> None:
    await delete_expired_scheduled_job_runs(
        now - settings.lnbits_scheduler_history_retention_days * 86400,
        now - settings.lnbits_scheduler_history_failed_retention_days * 86400,
    )
    await delete_excess_scheduled_job_runs(
        settings.lnbits_scheduler_history_max_runs_per_user,
        settings.lnbits_scheduler_history_max_runs_per_extension,
        preferred_status="failed",
    )


async def check_schedule_access(
    namespace: str, user_id: str | None, config: SchedulePolicy
) -> int | None:
    """Check current grants, including on executions after the user logs out."""
    if user_id:
        account = await get_account(user_id)
        if not account or not account.activated:
            raise PermissionError("Schedule owner is not active.")
    if namespace == "core":
        return None
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
    approved = None
    if extension.is_wasm:
        approved = _check_wasm_schedule_policy(
            extension.permissions, permission, config
        )
    if user_id:
        user_extension = await get_user_extension(user_id, extension_id)
        if not user_extension or not user_extension.active:
            raise PermissionError("Scheduled extension is not active for this user.")
    return (
        approved.max_jobs_per_user if isinstance(approved, UserSchedulePolicy) else None
    )


def _check_wasm_schedule_policy(
    permissions: list[ExtensionPermission], permission_id: str, config: SchedulePolicy
) -> SchedulePolicy:
    grant = next((item for item in permissions if item.id == permission_id), None)
    if not grant:
        raise PermissionError("Extension scheduling permission has been revoked.")
    try:
        approved = SchedulePolicy.parse_policies(
            grant.policies, user_scope=permission_id == SCHEDULER_USER_PERMISSION
        ).get(config.handler)
    except ValueError as exc:
        raise PermissionError("Invalid approved schedule policies.") from exc
    if not approved or (
        approved.cron_expression != config.cron_expression
        or approved.timezone != config.timezone
    ):
        raise PermissionError("Schedule does not match an admin-approved policy.")
    return approved


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
        self._next_interrupted_run_check = 0.0
        self._next_history_maintenance = 0.0

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
        max_jobs_per_user = await check_schedule_access(namespace, user_id, config)
        if (namespace, config.handler) not in self.handlers:
            raise ValueError("Schedule handler is not registered.")
        now = int(time.time())
        next_run = next_run_at(config.cron_expression, config.timezone, now)
        if next_run is None:
            raise ValueError("Cron expression has no occurrence within eight years.")
        # Updates remain allowed above the limit. Concurrent creates may exceed it.
        if (
            user_id
            and max_jobs_per_user is not None
            and not await get_scheduled_job(config.id)
        ):
            count = await get_scheduled_jobs_count(namespace, user_id, config.handler)
            if count >= max_jobs_per_user:
                raise ValueError(
                    "Scheduled job limit reached for this handler "
                    f"({max_jobs_per_user} per user)."
                )
        return await save_scheduled_job(
            ScheduledJob(
                **config.dict(),
                namespace=namespace,
                user_id=user_id,
                next_run_at=next_run,
            )
        )

    async def list_paginated(
        self,
        namespace: str,
        *,
        user_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Page[ScheduledJob]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid schedule pagination.")
        return await get_scheduled_jobs_paginated(
            namespace, user_id, limit=limit, offset=offset
        )

    async def delete(
        self, namespace: str, job_id: str, *, user_id: str | None = None
    ) -> bool:
        job = await get_scheduled_job(job_id)
        if not job or job.namespace != namespace or job.user_id != user_id:
            return False
        if job.lease_token and job.lease_until > int(time.time()):
            raise ValueError(
                "Job is running. Pause it and wait for it to stop before deleting."
            )
        return await delete_scheduled_job(job_id, namespace, user_id, int(time.time()))

    async def tick(self) -> None:
        if not settings.lnbits_scheduler_enabled:
            return
        now = time.time()
        if now >= self._next_interrupted_run_check:
            self._next_interrupted_run_check = now + 60
            try:
                await interrupt_expired_scheduled_job_runs(now)
            except Exception:
                logger.warning("Scheduler interrupted run check failed.")
        if now >= self._next_history_maintenance:
            self._next_history_maintenance = now + 15 * 60
            try:
                await maintain_scheduled_job_runs(now)
            except Exception:
                logger.warning("Scheduler history maintenance failed.")
        for job_id, (_, task) in list(self.running.items()):
            if task.done():
                # Workers handle callback errors, but database failures may escape.
                if not task.cancelled() and task.exception():
                    logger.warning("Scheduled job {} failed to finalize.", job_id)
                self.running.pop(job_id)
        available = self.concurrency - len(self.running)
        if available <= 0 or self.stopping or not settings.lnbits_scheduler_enabled:
            return
        await self._start_due_jobs(int(time.time()), available)

    async def _start_due_jobs(self, now: int, limit: int) -> None:
        for candidate in await get_due_scheduled_jobs(now, limit):
            if not settings.lnbits_scheduler_enabled:
                return
            if self.stopping or candidate.id in self.running:
                continue
            job = await claim_scheduled_job(
                candidate.id, uuid4().hex, now, now + self.lease_seconds
            )
            if job and not self.stopping:
                if not settings.lnbits_scheduler_enabled:
                    # The toggle may change while claiming; keep this job due.
                    await finish_scheduled_job(job, job.next_run_at)
                    return
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

    async def _execute(self, job: ScheduledJob) -> bool:
        current = await get_scheduled_job(job.id)
        if not current or not current.enabled or current.lease_token != job.lease_token:
            return False
        await check_schedule_access(current.namespace, current.user_id, current)
        callback = self.handlers.get((current.namespace, current.handler))
        if callback:
            await callback(current)
            return True
        return False

    async def _heartbeat(self, job: ScheduledJob) -> None:
        assert job.lease_token
        while settings.lnbits_running:
            await asyncio.sleep(self.lease_seconds / 3)
            await check_schedule_access(job.namespace, job.user_id, job)
            now = int(time.time())
            if not await renew_scheduled_job(
                job.id, job.lease_token, now, now + self.lease_seconds
            ):
                raise RuntimeError("Schedule claim lost or job paused.")

    async def _record_run_start(self, job: ScheduledJob) -> ScheduledJobRun | None:
        try:
            return await create_scheduled_job_run(job, time.time())
        except Exception:
            # Observability must not change whether a scheduled callback runs.
            logger.warning("Could not record scheduled job {} start.", job.id)
            return None

    async def _run_job(self, job: ScheduledJob) -> None:
        run = None
        work = None
        heartbeat = None
        cancelled = False
        status: ScheduledJobRunStatus = "succeeded"
        error_summary = None
        try:
            run = await self._record_run_start(job)
            work = asyncio.create_task(self._execute(job))
            heartbeat = asyncio.create_task(self._heartbeat(job))
            done, _ = await asyncio.wait(
                (work, heartbeat), return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                task.result()
            # The heartbeat only finishes by raising, so work is done here.
            if not work.result():
                status = "skipped"
                error_summary = (
                    "Job is unavailable, paused, or its handler is not registered."
                )
        except asyncio.CancelledError:
            cancelled = True
            status = "cancelled"
            error_summary = "Execution was cancelled."
            raise
        except Exception as exc:
            if heartbeat is not None and heartbeat.done():
                status = "cancelled"
                error_summary = "Scheduling access or the execution lease was lost."
            else:
                status = "failed"
                message = safe_error_message(str(exc))
                error_summary = (
                    f"{type(exc).__name__}: {message}"
                    if message
                    else type(exc).__name__
                )[:500]
            logger.warning(
                "Scheduled job {} failed ({}); next attempt follows its cron schedule.",
                job.id,
                error_summary,
            )
        finally:
            tasks: list[asyncio.Task] = [
                task for task in (work, heartbeat) if task is not None
            ]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if run:
                try:
                    await finish_scheduled_job_run(
                        run.id, status, time.time(), error_summary
                    )
                except Exception:
                    logger.warning("Could not record scheduled job {} result.", job.id)
            # On shutdown leave the durable lease to expire, so interrupted jobs
            # are recovered once on restart. Successful/failed jobs skip overlap.
            if not cancelled:
                following = next_run_at(
                    job.cron_expression, job.timezone, int(time.time())
                )
                await finish_scheduled_job(job, following)


scheduler = Scheduler()
_stop_tasks: set[asyncio.Task[None]] = set()


async def stop_scheduler_safely(timeout: float = 5.0) -> None:
    """Bound the shutdown wait while allowing in-flight cleanup to finish.

    Stop failures and caller cancellation are logged and suppressed.
    The deadline requires a responsive event loop and cannot kill native threads.
    """

    async def stop() -> None:
        try:
            await scheduler.stop()
        except asyncio.CancelledError:
            logger.warning("Scheduler shutdown was cancelled.")
        except Exception:
            logger.warning("Scheduler shutdown failed.")

    try:
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
    except asyncio.CancelledError:
        logger.warning(
            "Scheduler shutdown wait was cancelled; "
            "cleanup continues in the background."
        )
    except Exception:
        logger.warning("Scheduler shutdown failed.")
