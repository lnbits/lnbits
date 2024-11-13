import asyncio
import importlib
from typing import Optional

from loguru import logger

from lnbits.core import core_app_extra
from lnbits.core.crud import (
    create_installed_extension,
    delete_installed_extension,
    get_db_version,
    get_installed_extension,
    update_installed_extension_state,
)
from lnbits.core.crud.extensions import (
    get_installed_extensions,
    update_installed_extension,
)
from lnbits.core.helpers import migrate_extension_database
from lnbits.settings import settings

from ..models.extensions import Extension, ExtensionMeta, InstallableExtension


async def install_extension(ext_info: InstallableExtension) -> Extension:
    ext_id = ext_info.id
    extension = Extension.from_installable_ext(ext_info)
    installed_ext = await get_installed_extension(ext_id)
    if installed_ext and installed_ext.meta:
        ext_info.meta = ext_info.meta or ExtensionMeta()
        ext_info.meta.payments = installed_ext.meta.payments

    await ext_info.download_archive()

    ext_info.extract_archive()

    db_version = await get_db_version(ext_id)
    await migrate_extension_database(ext_info, db_version)

    # if the extensions does not exist in the installed extensions table, create it
    # if it does exist, it will be activated later in the code
    if not installed_ext:
        await create_installed_extension(ext_info)
    else:
        await update_installed_extension(ext_info)

    if extension.is_upgrade_extension:
        # call stop while the old routes are still active
        await stop_extension_background_work(ext_id)

    return extension


async def uninstall_extension(ext_id: str):
    await stop_extension_background_work(ext_id)

    settings.deactivate_extension_paths(ext_id)

    extension = await get_installed_extension(ext_id)
    if extension:
        extension.clean_extension_files()
    await delete_installed_extension(ext_id=ext_id)


async def activate_extension(ext: Extension):
    core_app_extra.register_new_ext_routes(ext)
    await update_installed_extension_state(ext_id=ext.code, active=True)


async def deactivate_extension(ext_id: str):
    settings.deactivate_extension_paths(ext_id)
    await update_installed_extension_state(ext_id=ext_id, active=False)


async def stop_extension_background_work(ext_id: str) -> bool:
    """
    Stop background work for extension (like asyncio.Tasks, WebSockets, etc).
    Extensions SHOULD expose a `api_stop()` function.
    """
    upgrade_hash = settings.extension_upgrade_hash(ext_id)
    ext = Extension(code=ext_id, is_valid=True, upgrade_hash=upgrade_hash)

    try:
        logger.info(f"Stopping background work for extension '{ext.module_name}'.")
        old_module = importlib.import_module(ext.module_name)

        # Extensions must expose an `{ext_id}_stop()` function at the module level
        # The `api_stop()` function is for backwards compatibility (will be deprecated)
        stop_fns = [f"{ext_id}_stop", "api_stop"]
        stop_fn_name = next((fn for fn in stop_fns if hasattr(old_module, fn)), None)
        assert stop_fn_name, f"No stop function found for '{ext.module_name}'."

        stop_fn = getattr(old_module, stop_fn_name)
        if stop_fn:
            if asyncio.iscoroutinefunction(stop_fn):
                await stop_fn()
            else:
                stop_fn()

        logger.info(f"Stopped background work for extension '{ext.module_name}'.")
    except Exception as ex:
        logger.warning(f"Failed to stop background work for '{ext.module_name}'.")
        logger.warning(ex)
        return False

    return True


async def get_valid_extensions(
    include_deactivated: Optional[bool] = True,
) -> list[Extension]:
    installed_extensions = await get_installed_extensions()
    valid_extensions = [Extension.from_installable_ext(e) for e in installed_extensions]

    if include_deactivated:
        return valid_extensions

    if settings.lnbits_extensions_deactivate_all:
        return []

    return [
        e
        for e in valid_extensions
        if e.code not in settings.lnbits_deactivated_extensions
    ]


async def get_valid_extension(
    ext_id: str, include_deactivated: Optional[bool] = True
) -> Optional[Extension]:
    ext = await get_installed_extension(ext_id)
    if not ext:
        return None

    if include_deactivated:
        return Extension.from_installable_ext(ext)

    if settings.lnbits_extensions_deactivate_all:
        return None

    return Extension.from_installable_ext(ext)
