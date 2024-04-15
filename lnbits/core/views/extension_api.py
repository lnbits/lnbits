from http import HTTPStatus
from typing import (
    List,
    Optional,
)

from bolt11 import decode as bolt11_decode
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from loguru import logger

from lnbits.core.db import core_app_extra
from lnbits.core.helpers import (
    migrate_extension_database,
    stop_extension_background_work,
)
from lnbits.core.models import (
    User,
)
from lnbits.decorators import (
    check_access_token,
    check_admin,
)
from lnbits.extension_manager import (
    CreateExtension,
    Extension,
    ExtensionRelease,
    InstallableExtension,
    fetch_github_release_config,
    fetch_release_payment_info,
    get_valid_extensions,
)
from lnbits.settings import settings

from ..crud import (
    add_installed_extension,
    delete_dbversion,
    delete_installed_extension,
    drop_extension_db,
    get_dbversions,
    get_installed_extension,
    get_installed_extensions,
)

extension_router = APIRouter(
    tags=["Extension Managment"],
    prefix="/api/v1/extension",
)


@extension_router.post("")
async def api_install_extension(
    data: CreateExtension,
    user: User = Depends(check_admin),
    access_token: Optional[str] = Depends(check_access_token),
):
    release = await InstallableExtension.get_extension_release(
        data.ext_id, data.source_repo, data.archive, data.version
    )
    if not release:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Release not found"
        )

    if not release.is_version_compatible:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Incompatible extension version"
        )

    release.payment_hash = data.payment_hash
    ext_info = InstallableExtension(
        id=data.ext_id, name=data.ext_id, installed_release=release, icon=release.icon
    )

    try:
        installed_ext = await get_installed_extension(data.ext_id)
        ext_info.payments = installed_ext.payments if installed_ext else []

        await ext_info.download_archive()

        ext_info.extract_archive()

        extension = Extension.from_installable_ext(ext_info)

        db_version = (await get_dbversions()).get(data.ext_id, 0)
        await migrate_extension_database(extension, db_version)

        await add_installed_extension(ext_info)

        if extension.is_upgrade_extension:
            # call stop while the old routes are still active
            await stop_extension_background_work(data.ext_id, user.id, access_token)

        if data.ext_id not in settings.lnbits_deactivated_extensions:
            settings.lnbits_deactivated_extensions += [data.ext_id]

        # mount routes for the new version
        core_app_extra.register_new_ext_routes(extension)

        if extension.upgrade_hash:
            ext_info.notify_upgrade()

        return extension
    except AssertionError as e:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(e))
    except Exception as ex:
        logger.warning(ex)
        ext_info.clean_extension_files()
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=(
                f"Failed to install extension {ext_info.id} "
                f"({ext_info.installed_version})."
            ),
        )


@extension_router.delete("/{ext_id}")
async def api_uninstall_extension(
    ext_id: str,
    user: User = Depends(check_admin),
    access_token: Optional[str] = Depends(check_access_token),
):
    installed_extensions = await get_installed_extensions()

    extensions = [e for e in installed_extensions if e.id == ext_id]
    if len(extensions) == 0:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Unknown extension id: {ext_id}",
        )

    # check that other extensions do not depend on this one
    for valid_ext_id in [ext.code for ext in get_valid_extensions()]:
        installed_ext = next(
            (ext for ext in installed_extensions if ext.id == valid_ext_id), None
        )
        if installed_ext and ext_id in installed_ext.dependencies:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=(
                    f"Cannot uninstall. Extension '{installed_ext.name}' "
                    "depends on this one."
                ),
            )

    try:
        # call stop while the old routes are still active
        await stop_extension_background_work(ext_id, user.id, access_token)

        if ext_id not in settings.lnbits_deactivated_extensions:
            settings.lnbits_deactivated_extensions += [ext_id]

        for ext_info in extensions:
            ext_info.clean_extension_files()
            await delete_installed_extension(ext_id=ext_info.id)

        logger.success(f"Extension '{ext_id}' uninstalled.")
    except Exception as ex:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(ex)
        )


@extension_router.get("/{ext_id}/releases", dependencies=[Depends(check_admin)])
async def get_extension_releases(ext_id: str):
    try:
        extension_releases: List[ExtensionRelease] = (
            await InstallableExtension.get_extension_releases(ext_id)
        )

        installed_ext = await get_installed_extension(ext_id)
        if not installed_ext:
            return extension_releases

        for release in extension_releases:
            payment_info = installed_ext.find_existing_payment(release.pay_link)
            if payment_info:
                release.paid_sats = payment_info.amount

        return extension_releases

    except Exception as ex:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(ex)
        )


@extension_router.put("/invoice", dependencies=[Depends(check_admin)])
async def get_extension_invoice(data: CreateExtension):
    try:
        assert data.cost_sats, "A non-zero amount must be specified"
        release = await InstallableExtension.get_extension_release(
            data.ext_id, data.source_repo, data.archive, data.version
        )
        assert release, "Release not found"
        assert release.pay_link, "Pay link not found for release"

        payment_info = await fetch_release_payment_info(
            release.pay_link, data.cost_sats
        )
        assert payment_info and payment_info.payment_request, "Cannot request invoice"
        invoice = bolt11_decode(payment_info.payment_request)

        assert invoice.amount_msat is not None, "Invoic amount is missing"
        invoice_amount = int(invoice.amount_msat / 1000)
        assert (
            invoice_amount == data.cost_sats
        ), f"Wrong invoice amount: {invoice_amount}."
        assert (
            payment_info.payment_hash == invoice.payment_hash
        ), "Wroong invoice payment hash"

        return payment_info

    except AssertionError as e:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(e))
    except Exception as ex:
        logger.warning(ex)
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Cannot request invoice")


@extension_router.get(
    "/release/{org}/{repo}/{tag_name}",
    dependencies=[Depends(check_admin)],
)
async def get_extension_release(org: str, repo: str, tag_name: str):
    try:
        config = await fetch_github_release_config(org, repo, tag_name)
        if not config:
            return {}

        return {
            "min_lnbits_version": config.min_lnbits_version,
            "is_version_compatible": config.is_version_compatible(),
            "warning": config.warning,
        }
    except Exception as ex:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(ex)
        )


@extension_router.delete(
    "/{ext_id}/db",
    dependencies=[Depends(check_admin)],
)
async def delete_extension_db(ext_id: str):
    try:
        db_version = (await get_dbversions()).get(ext_id, None)
        if not db_version:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Unknown extension id: {ext_id}",
            )
        await drop_extension_db(ext_id=ext_id)
        await delete_dbversion(ext_id=ext_id)
        logger.success(f"Database removed for extension '{ext_id}'")
    except HTTPException as ex:
        logger.error(ex)
        raise ex
    except Exception as ex:
        logger.error(ex)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Cannot delete data for extension '{ext_id}'",
        )
