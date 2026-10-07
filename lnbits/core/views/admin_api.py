import base64
import json
import os
import time
from http import HTTPStatus
from pathlib import Path
from shutil import make_archive
from subprocess import Popen
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, Header, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import SecretStr
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from starlette.concurrency import run_in_threadpool

from lnbits.core.models.notifications import NotificationType
from lnbits.core.models.users import Account
from lnbits.core.services import (
    enqueue_admin_notification,
    get_balance_delta,
    update_cached_settings,
)
from lnbits.core.services.notifications import send_email_notification
from lnbits.core.services.onchain import (
    OnchainKeyStatus,
    confirm_onchain_key_backup,
    onchain_key_status,
    read_onchain_key,
    setup_onchain_key,
)
from lnbits.core.services.settings import dict_to_settings
from lnbits.decorators import check_admin, check_super_user
from lnbits.server import server_restart
from lnbits.settings import AdminSettings, Settings, UpdateSettings, settings
from lnbits.task_manager import PublicTask, task_manager

from .. import core_app_extra
from ..crud import get_admin_settings, reset_core_settings, update_admin_settings

admin_router = APIRouter(tags=["Admin UI"], prefix="/admin")
file_upload = File(...)


@admin_router.get(
    "/api/v1/audit",
    name="Audit",
    description="show the current balance of the node and the LNbits database",
    dependencies=[Depends(check_admin)],
)
async def api_auditor():
    return await get_balance_delta()


@admin_router.get(
    "/api/v1/monitor",
    name="Monitor",
    description="show the current listeners and other monitoring data",
    dependencies=[Depends(check_admin)],
    response_model=list[PublicTask],
)
async def api_monitor() -> list[PublicTask]:
    return task_manager.get_public_tasks()


@admin_router.get(
    "/api/v1/testemail",
    name="TestEmail",
    description="send a test email to the admin",
    dependencies=[Depends(check_admin)],
)
async def api_test_email():
    return await send_email_notification(
        settings.lnbits_email_notifications_to_emails,
        "This is a LNbits test email.",
        "LNbits Test Email",
    )


@admin_router.get("/api/v1/settings")
async def api_get_settings(
    account: Account = Depends(check_admin),
) -> AdminSettings | None:
    admin_settings = await get_admin_settings(account.is_super_user)
    return admin_settings


@admin_router.put(
    "/api/v1/settings",
    status_code=HTTPStatus.OK,
)
async def api_update_settings(
    data: UpdateSettings, account: Account = Depends(check_admin)
):
    if "lnbits_allow_onchain_payments" in data.__fields_set__:
        enabled = data.lnbits_allow_onchain_payments
        if (
            enabled != settings.lnbits_allow_onchain_payments
            and not account.is_super_user
        ):
            raise HTTPException(
                HTTPStatus.FORBIDDEN, "Only the super user can change onchain payments."
            )
        if enabled:
            status = await onchain_key_status()
            if not status.configured or not status.backup_confirmed:
                raise HTTPException(
                    HTTPStatus.CONFLICT,
                    "Set up and back up the onchain encryption key "
                    "before enabling onchain payments.",
                )
    enqueue_admin_notification(
        NotificationType.settings_update, {"username": account.username}
    )
    await update_admin_settings(data)
    admin_settings = await get_admin_settings(account.is_super_user)
    if not admin_settings:
        raise ValueError("Updated admin settings not found.")
    update_cached_settings(admin_settings.dict())
    core_app_extra.register_new_ratelimiter()
    return {"status": "Success"}


@admin_router.get("/api/v1/onchain/key", dependencies=[Depends(check_super_user)])
async def api_onchain_key_status(response: Response) -> OnchainKeyStatus:
    response.headers["Cache-Control"] = "no-store"
    return await onchain_key_status()


@admin_router.post("/api/v1/onchain/key", dependencies=[Depends(check_super_user)])
async def api_setup_onchain_key(
    response: Response,
    recovery_key: Annotated[
        SecretStr | None, Header(alias="X-Onchain-Recovery-Key")
    ] = None,
) -> OnchainKeyStatus:
    response.headers["Cache-Control"] = "no-store"
    try:
        return await setup_onchain_key(
            recovery_key.get_secret_value() if recovery_key else None
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            "Cannot set up the onchain key. Check the recovery key, "
            "existing configuration and data-folder permissions.",
        ) from exc


@admin_router.post(
    "/api/v1/onchain/key/backup", dependencies=[Depends(check_super_user)]
)
async def api_backup_onchain_key() -> Response:
    try:
        status = await setup_onchain_key()
        key = await run_in_threadpool(read_onchain_key)
    except (ValueError, OSError) as exc:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            "The onchain key is unavailable. Restore its original backup.",
        ) from exc
    return Response(
        content=json.dumps(
            {
                "version": 1,
                "key": base64.b64encode(key).decode(),
                "fingerprint": status.fingerprint,
            },
            indent=2,
        ),
        media_type="application/json",
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "Content-Disposition": 'attachment; filename="lnbits-onchain-key.json"',
        },
    )


@admin_router.post(
    "/api/v1/onchain/key/confirm", dependencies=[Depends(check_super_user)]
)
async def api_confirm_onchain_key_backup(
    fingerprint: Annotated[str, Header(alias="X-Onchain-Key-Fingerprint")],
    response: Response,
) -> OnchainKeyStatus:
    response.headers["Cache-Control"] = "no-store"
    try:
        return await confirm_onchain_key_backup(fingerprint)
    except (ValueError, OSError) as exc:
        raise HTTPException(
            HTTPStatus.CONFLICT, "The backup does not match the onchain key."
        ) from exc


@admin_router.patch(
    "/api/v1/settings",
    status_code=HTTPStatus.OK,
)
async def api_update_settings_partial(
    data: dict, account: Account = Depends(check_admin)
):
    updatable_settings = dict_to_settings({**settings.dict(), **data})
    return await api_update_settings(updatable_settings, account)


@admin_router.get(
    "/api/v1/settings/default",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def api_reset_settings(field_name: str):
    default_settings = Settings()
    return {"default_value": getattr(default_settings, field_name)}


@admin_router.delete("/api/v1/settings", status_code=HTTPStatus.OK)
async def api_delete_settings(account: Account = Depends(check_super_user)) -> None:
    enqueue_admin_notification(
        NotificationType.settings_update, {"username": account.username}
    )
    await reset_core_settings()
    server_restart.set()


@admin_router.get(
    "/api/v1/restart",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def api_restart_server() -> dict[str, str]:
    server_restart.set()
    return {"status": "Success"}


@admin_router.get(
    "/api/v1/backup",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
    response_class=FileResponse,
)
async def api_download_backup() -> FileResponse:
    last_filename = "lnbits-backup"
    filename = f"lnbits-backup-{int(time.time())}.zip"
    db_url = settings.lnbits_database_url
    pg_backup_filename = Path(settings.lnbits_data_folder) / "lnbits-database.dmp"
    is_pg = db_url and db_url.startswith("postgres://")

    if is_pg and db_url:
        env = _build_pg_dump_env(db_url)
        try:
            proc = Popen(
                [
                    "pg_dump",
                    "--no-password",
                    "--format=c",
                    f"--file={pg_backup_filename}",
                ],
                shell=False,
                env=env,
            )
            if proc.wait() != 0:
                raise ValueError("PostgreSQL database backup failed.")
            make_archive(last_filename, "zip", settings.lnbits_data_folder)
        finally:
            pg_backup_filename.unlink(missing_ok=True)
    else:
        make_archive(last_filename, "zip", settings.lnbits_data_folder)

    return FileResponse(
        path=f"{last_filename}.zip",
        filename=filename,
        media_type="application/zip",
        headers={"Cache-Control": "no-store"},
    )


def _build_pg_dump_env(database_url: str) -> dict[str, str]:
    try:
        url = cast(URL, make_url(database_url))
    except (ArgumentError, ValueError) as exc:
        raise ValueError("Invalid PostgreSQL database URL.") from exc
    if url.drivername != "postgres":
        raise ValueError("Invalid PostgreSQL database URL.")

    # Match the connection arguments used by SQLAlchemy's asyncpg dialect.
    parameters = url.translate_connect_args(username="user")
    parameters.update(url.query)
    env = os.environ.copy()
    for parameter, variable in {
        "host": "PGHOST",
        "port": "PGPORT",
        "user": "PGUSER",
        "password": "PGPASSWORD",
        "database": "PGDATABASE",
        "ssl": "PGSSLMODE",
    }.items():
        value = parameters.get(parameter)
        if value is not None:
            env[variable] = ",".join(value) if isinstance(value, tuple) else str(value)
    return env
