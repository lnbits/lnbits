import os
import time
from http import HTTPStatus
from pathlib import Path
from shutil import make_archive, move
from subprocess import Popen
from tempfile import NamedTemporaryFile
from typing import IO, Optional
from urllib.parse import urlparse

import filetype
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from lnbits.core.models import User
from lnbits.core.models.misc import Image, SimpleStatus
from lnbits.core.models.notifications import NotificationType
from lnbits.core.services import (
    enqueue_notification,
    get_balance_delta,
    update_cached_settings,
)
from lnbits.core.services.notifications import send_email_notification
from lnbits.core.services.settings import dict_to_settings
from lnbits.decorators import check_admin, check_super_user
from lnbits.helpers import safe_upload_file_path
from lnbits.server import server_restart
from lnbits.settings import AdminSettings, Settings, UpdateSettings, settings
from lnbits.tasks import invoice_listeners

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
)
async def api_monitor():
    return {
        "invoice_listeners": list(invoice_listeners.keys()),
    }


@admin_router.get(
    "/api/v1/testemail",
    name="TestEmail",
    description="send a test email to the admin",
    dependencies=[Depends(check_admin)],
)
async def api_test_email():
    return await send_email_notification(
        "This is a LNbits test email.", "LNbits Test Email"
    )


@admin_router.get("/api/v1/settings", response_model=Optional[AdminSettings])
async def api_get_settings(
    user: User = Depends(check_admin),
) -> Optional[AdminSettings]:
    admin_settings = await get_admin_settings(user.super_user)
    return admin_settings


@admin_router.put(
    "/api/v1/settings",
    status_code=HTTPStatus.OK,
)
async def api_update_settings(data: UpdateSettings, user: User = Depends(check_admin)):
    enqueue_notification(NotificationType.settings_update, {"username": user.username})
    await update_admin_settings(data)
    admin_settings = await get_admin_settings(user.super_user)
    assert admin_settings, "Updated admin settings not found."
    update_cached_settings(admin_settings.dict())
    core_app_extra.register_new_ratelimiter()
    return {"status": "Success"}


@admin_router.patch(
    "/api/v1/settings",
    status_code=HTTPStatus.OK,
)
async def api_update_settings_partial(data: dict, user: User = Depends(check_admin)):
    updatable_settings = dict_to_settings({**settings.dict(), **data})
    return await api_update_settings(updatable_settings, user)


@admin_router.get(
    "/api/v1/settings/default",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def api_reset_settings(field_name: str):
    default_settings = Settings()
    return {"default_value": getattr(default_settings, field_name)}


@admin_router.delete("/api/v1/settings", status_code=HTTPStatus.OK)
async def api_delete_settings(user: User = Depends(check_super_user)) -> None:
    enqueue_notification(NotificationType.settings_update, {"username": user.username})
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


@admin_router.post(
    "/api/v1/images",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def upload_image(
    file: UploadFile = file_upload,
    content_length: int = Header(..., le=settings.lnbits_upload_size_bytes),
) -> Image:
    if not file.filename:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="No filename provided."
        )

    # validate file types
    file_info = filetype.guess(file.file)
    if file_info is None:
        raise HTTPException(
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            detail="Unable to determine file type",
        )
    detected_content_type = file_info.extension.lower()
    if (
        file.content_type not in settings.lnbits_upload_allowed_types
        or detected_content_type not in settings.lnbits_upload_allowed_types
    ):
        raise HTTPException(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Unsupported file type")

    # validate file name
    try:
        file_path = safe_upload_file_path(file.filename)
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=f"The requested filename '{file.filename}' is forbidden.",
        ) from e

    # validate file size
    real_file_size = 0
    temp: IO = NamedTemporaryFile(delete=False)
    for chunk in file.file:
        real_file_size += len(chunk)
        if real_file_size > content_length:
            raise HTTPException(
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large ({content_length / 1000} KB max)",
            )
        temp.write(chunk)
    temp.close()

    move(temp.name, file_path)
    return Image(filename=file.filename)


@admin_router.get(
    "/api/v1/images",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def list_uploaded_images() -> list[Image]:
    image_folder = Path(settings.lnbits_data_folder, "images")
    files = image_folder.glob("*")
    images = []
    for file in files:
        if file.is_file():
            images.append(Image(filename=file.name))
    return images


@admin_router.delete(
    "/api/v1/images/{filename}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def delete_uploaded_image(filename: str) -> SimpleStatus:
    try:
        file_path = safe_upload_file_path(filename)
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=f"The requested filename '{filename}' is forbidden.",
        ) from e

    if not file_path.exists():
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Image not found.")

    file_path.unlink()
    return SimpleStatus(success=True, message=f"{filename} deleted")
