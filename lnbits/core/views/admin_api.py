import os
import time
from http import HTTPStatus
from shutil import make_archive
from subprocess import Popen
from typing import Optional
from urllib.parse import urlparse

from fastapi import Body, Depends
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_wallet
from lnbits.core.models import User
from lnbits.core.services import update_cached_settings, update_wallet_balance
from lnbits.decorators import check_admin, check_super_user
from lnbits.server import server_restart
from lnbits.settings import AdminSettings, EditableSettings, settings

from .. import core_app
from ..crud import delete_admin_settings, get_admin_settings, update_admin_settings


@core_app.get("/admin/api/v1/settings/")
async def api_get_settings(
    user: User = Depends(check_admin),
) -> Optional[AdminSettings]:
    admin_settings = await get_admin_settings(user.super_user)
    return admin_settings


@core_app.put(
    "/admin/api/v1/settings/",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def api_update_settings(data: EditableSettings):
    await update_admin_settings(data)
    update_cached_settings(dict(data))
    return {"status": "Success"}


@core_app.delete(
    "/admin/api/v1/settings/",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def api_delete_settings() -> None:
    await delete_admin_settings()
    server_restart.set()


@core_app.get(
    "/admin/api/v1/restart/",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def api_restart_server() -> dict[str, str]:
    server_restart.set()
    return {"status": "Success"}


@core_app.put(
    "/admin/api/v1/topup/",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def api_topup_balance(
    id: str = Body(...), amount: int = Body(...)
) -> dict[str, str]:
    try:
        await get_wallet(id)
    except:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="wallet does not exist."
        )

    await update_wallet_balance(wallet_id=id, amount=int(amount))

    return {"status": "Success"}


@core_app.get(
    "/admin/api/v1/backup/",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
    response_class=FileResponse,
)
async def api_download_backup() -> FileResponse:
    last_filename = "lnbits-backup"
    filename = f"lnbits-backup-{int(time.time())}.zip"
    db_url = settings.lnbits_database_url
    pg_backup_filename = f"{settings.lnbits_data_folder}/lnbits-database.dmp"
    is_pg = db_url and db_url.startswith("postgres://")

    if is_pg:
        p = urlparse(db_url)
        command = (
            f"pg_dump --host={p.hostname} "
            f'--dbname={p.path.replace("/", "")} '
            f"--username={p.username} "
            f"--no-password "
            f"--format=c "
            f"--file={pg_backup_filename}"
        )
        proc = Popen(
            command, shell=True, env={**os.environ, "PGPASSWORD": p.password or ""}
        )
        proc.wait()

    make_archive(last_filename, "zip", settings.lnbits_data_folder)

    # cleanup pg_dump file
    if is_pg:
        proc = Popen(f"rm {pg_backup_filename}", shell=True)
        proc.wait()

    return FileResponse(
        path=f"{last_filename}.zip", filename=filename, media_type="application/zip"
    )
