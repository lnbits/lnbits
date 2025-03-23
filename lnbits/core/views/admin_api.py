import glob
import imghdr
import os
import time
import uuid
from http import HTTPStatus
from io import BytesIO
from shutil import make_archive
from subprocess import Popen
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile
from fastapi.responses import FileResponse

from lnbits.core.models import User
from lnbits.core.models.notifications import NotificationType
from lnbits.core.services import (
    enqueue_notification,
    get_balance_delta,
    update_cached_settings,
)
from lnbits.core.services.notifications import send_email_notification
from lnbits.core.services.settings import dict_to_settings
from lnbits.decorators import check_admin, check_super_user
from lnbits.server import server_restart
from lnbits.settings import AdminSettings, Settings, UpdateSettings, settings
from lnbits.tasks import invoice_listeners

from .. import core_app_extra
from ..crud import delete_admin_settings, get_admin_settings, update_admin_settings

admin_router = APIRouter(tags=["Admin UI"], prefix="/admin")


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
    await delete_admin_settings()
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
    "/api/v1/upload",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def upload_image(file: UploadFile = File(...)):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.split(".")[-1].lower()
    if ext not in {"png", "jpg", "jpeg", "gif"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    contents = BytesIO()
    total_size = 0

    while chunk := await file.read(1024 * 1024):
        total_size += len(chunk)
        if total_size > 2 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large")
        contents.write(chunk)

    contents.seek(0)

    kind = imghdr.what(None, h=contents.read(512))
    if kind not in {"png", "jpeg", "gif"}:
        raise HTTPException(status_code=400, detail="Invalid image file")
    contents.seek(0)

    filename = f"{uuid.uuid4()}.{ext}"
    image_folder = os.path.join(settings.lnbits_data_folder, "images")
    os.makedirs(image_folder, exist_ok=True)
    file_path = os.path.join(image_folder, filename)

    with open(file_path, "wb") as f:
        f.write(contents.read())

    return {"filename": filename, "url": f"/static/images/{filename}"}


@admin_router.get(
    "/api/v1/images",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def list_uploaded_images():
    image_folder = os.path.join(settings.lnbits_data_folder, "images")
    if not os.path.exists(image_folder):
        return []

    files = glob.glob(os.path.join(image_folder, "*"))
    images = []

    for file_path in files:
        if os.path.isfile(file_path):
            filename = os.path.basename(file_path)
            images.append({"filename": filename, "url": f"/static/images/{filename}"})

    return images


@admin_router.delete(
    "/api/v1/images/{filename}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def delete_uploaded_image(
    filename: str = Path(..., description="Name of the image file to delete")
):
    image_folder = os.path.join(settings.lnbits_data_folder, "images")
    file_path = os.path.join(image_folder, filename)

    # Prevent directory traversal attack (e.g., filename = "../../etc/passwd")
    if not os.path.abspath(file_path).startswith(os.path.abspath(image_folder)):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")

    os.remove(file_path)
    return {"status": "success", "message": f"{filename} deleted"}
