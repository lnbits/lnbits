import json

from lnbits.core.crud.users import get_account
from lnbits.core.db import core_app_extra
from lnbits.core.models.scheduler import ScheduledJob
from lnbits.core.services.scheduler import scheduler

from .invoke import invoke_wasm_extension_export
from .loader import WasmExtension


def register_wasm_schedule_handlers(extension: WasmExtension) -> None:
    namespace = f"extension:{extension.id}"
    scheduler.unregister(namespace)
    for export in extension.exports:
        if export.visibility == "event":
            scheduler.register(namespace, export.name, dispatch_wasm_schedule)


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
        context="schedule",
        trigger_type="schedule",
        context_data={"schedule_id": job.id},
    )
