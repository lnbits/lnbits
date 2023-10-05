import os
import time
from http import HTTPStatus
from shutil import make_archive
from subprocess import Popen
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_wallet
from lnbits.core.models import CreateTopup
from lnbits.core.services import (
    update_wallet_balance,
)
from lnbits.decorators import check_super_user
from lnbits.server import server_restart
from lnbits.settings import settings

from ..crud import delete_admin_settings

superuser_router = APIRouter(
    prefix="/superuser/api/v1",
    dependencies=[Depends(check_super_user)],
)


@superuser_router.delete(
    "/settings/",
    status_code=HTTPStatus.OK,
)
async def api_delete_settings() -> None:
    await delete_admin_settings()
    server_restart.set()


@superuser_router.get(
    "/restart/",
    status_code=HTTPStatus.OK,
)
async def api_restart_server() -> dict[str, str]:
    server_restart.set()
    return {"status": "Success"}


@superuser_router.put(
    "/topup/",
    name="Topup",
    status_code=HTTPStatus.OK,
)
async def api_topup_balance(data: CreateTopup) -> dict[str, str]:
    try:
        await get_wallet(data.id)
    except Exception:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="wallet does not exist."
        )

    if settings.lnbits_backend_wallet_class == "VoidWallet":
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="VoidWallet active"
        )

    await update_wallet_balance(wallet_id=data.id, amount=int(data.amount))

    return {"status": "Success"}


@superuser_router.get(
    "/backup/",
    status_code=HTTPStatus.OK,
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
            f"--dbname={p.path.replace('/', '')} "
            f"--username={p.username} "
            "--no-password "
            "--format=c "
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
