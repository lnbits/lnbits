import os
import shutil
from hashlib import sha256

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from lnbits.core.models import (
    SimpleStatus,
    User,
)
from lnbits.core.models.extensions import (
    Extension,
    ExtensionMeta,
    InstallableExtension,
    UserExtension,
)
from lnbits.core.models.extensions_builder import ExtensionData
from lnbits.core.services.extensions import (
    activate_extension,
    install_extension,
)
from lnbits.core.services.extensions_builder import (
    build_extension_from_data,
    clean_extension_builder_data,
    zip_directory,
)
from lnbits.decorators import (
    check_admin,
    check_extension_builder,
    check_user_exists,
)

from ..crud import (
    create_user_extension,
    get_user_extension,
    update_user_extension,
)

extension_builder_router = APIRouter(
    tags=["Extension Managment"],
    prefix="/api/v1/extension/builder",
)


@extension_builder_router.post(
    "/zip",
    summary="Build and download extension zip.",
    dependencies=[Depends(check_extension_builder)],
    description="""
        This endpoint generates a zip file for the extension based on the provided data.
    """,
)
async def api_build_extension(data: ExtensionData) -> FileResponse:
    stub_ext_id = "extension_builder_stub"  # todo: do not hardcode, fetch from manifest
    release, build_dir = await build_extension_from_data(data, stub_ext_id)

    ext_info = InstallableExtension(
        id=data.id,
        name=data.name,
        version="0.1.0",
        short_description=data.short_description,
        meta=ExtensionMeta(installed_release=release),
    )
    ext_zip_file = ext_info.zip_path
    if ext_zip_file.is_file():
        os.remove(ext_zip_file)

    zip_directory(build_dir, ext_zip_file)
    shutil.rmtree(build_dir, True)

    return FileResponse(
        ext_zip_file, filename=f"{data.id}.zip", media_type="application/zip"
    )


@extension_builder_router.post(
    "/deploy",
    summary="Build extension based on provided config.",
    description="""
        This endpoint generates a zip file for the extension based on the provided data.
        If `deploy` is set to true, the extension will be installed and activated.
    """,
)
async def api_deploy_extension(
    data: ExtensionData,
    user: User = Depends(check_admin),
) -> SimpleStatus:
    working_dir_name = "deploy_" + sha256(user.id.encode("utf-8")).hexdigest()
    stub_ext_id = "extension_builder_stub"
    release, build_dir = await build_extension_from_data(
        data, stub_ext_id, working_dir_name
    )

    ext_info = InstallableExtension(
        id=data.id,
        name=data.name,
        version="0.1.0",
        short_description=data.short_description,
        meta=ExtensionMeta(installed_release=release),
        icon=release.icon,
    )
    ext_zip_file = ext_info.zip_path
    if ext_zip_file.is_file():
        os.remove(ext_zip_file)

    zip_directory(build_dir.parent, ext_zip_file)

    await install_extension(ext_info, skip_download=True)

    await activate_extension(Extension.from_installable_ext(ext_info))

    user_ext = await get_user_extension(user.id, data.id)
    if not user_ext:
        user_ext = UserExtension(user=user.id, extension=data.id, active=True)
        await create_user_extension(user_ext)
    elif not user_ext.active:
        user_ext.active = True
    await update_user_extension(user_ext)

    return SimpleStatus(success=True, message=f"Extension '{data.id}' deployed.")


@extension_builder_router.post(
    "/preview",
    summary="Build and preview the extension ui.",
    dependencies=[Depends(check_extension_builder)],
)
async def api_preview_extension(
    data: ExtensionData,
    user: User = Depends(check_user_exists),
) -> SimpleStatus:
    stub_ext_id = "extension_builder_stub"
    working_dir_name = "preview_" + sha256(user.id.encode("utf-8")).hexdigest()
    await build_extension_from_data(data, stub_ext_id, working_dir_name)

    return SimpleStatus(success=True, message=f"Extension '{data.id}' preview ready.")


@extension_builder_router.delete(
    "",
    summary="Clean extension builder data.",
    description="""
        This endpoint cleans the extension builder data.
    """,
    dependencies=[Depends(check_admin)],
)
async def api_delete_extension_builder_data() -> SimpleStatus:

    clean_extension_builder_data()

    return SimpleStatus(success=True, message="Extension Builder data cleaned.")
