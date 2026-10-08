import json

from lnbits.core.crud.scheduler import get_scheduled_job
from lnbits.core.crud.users import get_account
from lnbits.core.db import core_app_extra
from lnbits.core.models.scheduler import ScheduleConfig, ScheduledJob
from lnbits.core.services.scheduler import check_schedule_access, scheduler
from lnbits.helpers import sha256s

from .invoke import invoke_wasm_extension_export
from .loader import WasmExtension


def register_wasm_schedule_handlers(extension: WasmExtension) -> None:
    namespace = f"extension:{extension.id}"
    scheduler.unregister(namespace)
    for export in extension.exports:
        if export.visibility == "event":
            scheduler.register(namespace, export.name, dispatch_wasm_schedule)


async def ensure_wasm_extension_schedules(ext_id: str) -> None:
    extension = core_app_extra.wasm_extension_registry.get(ext_id)
    if not extension:
        raise ValueError("WASM extension must be registered before starting schedules.")
    namespace = f"extension:{ext_id}"
    for policy in extension.config.schedules:
        await check_schedule_access(namespace, None, policy)
        job_id = sha256s(json.dumps([ext_id, None, policy.handler]))
        existing = await get_scheduled_job(job_id)
        if existing and (
            existing.cron_expression == policy.cron_expression
            and existing.timezone == policy.timezone
        ):
            # Preserve the next run, any running lease, and administrator pauses.
            continue
        await scheduler.save(
            namespace,
            ScheduleConfig(
                **policy.dict(),
                id=job_id,
                enabled=existing.enabled if existing else True,
            ),
        )


async def dispatch_wasm_schedule(job: ScheduledJob) -> None:
    extension_id = job.namespace.removeprefix("extension:")
    extension = core_app_extra.wasm_extension_registry.get(extension_id)
    if not extension or not any(
        export.name == job.handler and export.visibility == "event"
        for export in extension.exports
    ):
        raise PermissionError("Scheduled WASM handler is not an event export.")
    user = await get_account(job.user_id) if job.user_id else None
    if job.user_id and (not user or not user.activated):
        raise PermissionError("Scheduled user is no longer active.")
    await invoke_wasm_extension_export(
        extension_id,
        job.handler,
        {
            "scheduleId": job.id,
            "scheduledAt": job.next_run_at,
            "data": json.loads(job.payload_json),
        },
        user=user,
        # Extension jobs own a separate partition, never an administrator's data.
        # Users can read selected fields through the existing public-storage API.
        owner_id=f"extension:{extension_id}" if not job.user_id else None,
        context="schedule",
        trigger_type="schedule",
        context_data={"schedule_id": job.id},
    )
