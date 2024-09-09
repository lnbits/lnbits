import asyncio
import importlib

from loguru import logger

from lnbits.core.crud import (
    delete_installed_extension,
    get_installed_extension,
    update_installed_extension_state,
)
from lnbits.core.db import core_app_extra
from lnbits.settings import settings

from .models import Extension


async def activate_extension(ext: Extension):
    core_app_extra.register_new_ext_routes(ext)
    await update_installed_extension_state(ext_id=ext.code, active=True)


async def deactivate_extension(ext_id: str):
    settings.deactivate_extension_paths(ext_id)
    await update_installed_extension_state(ext_id=ext_id, active=False)


async def uninstall_extension(ext_id):
    await stop_extension_background_work(ext_id)

    settings.deactivate_extension_paths(ext_id)

    extension = await get_installed_extension(ext_id)
    if extension:
        extension.clean_extension_files()
    await delete_installed_extension(ext_id=ext_id)


async def stop_extension_background_work(ext_id) -> bool:
    """
    Stop background work for extension (like asyncio.Tasks, WebSockets, etc).
    Extensions SHOULD expose a `api_stop()` function.
    """
    upgrade_hash = settings.extension_upgrade_hash(ext_id) or ""
    ext = Extension(ext_id, True, False, upgrade_hash=upgrade_hash)

    try:
        logger.info(f"Stopping background work for extension '{ext.module_name}'.")
        old_module = importlib.import_module(ext.module_name)

        # Extensions must expose an `{ext_id}_stop()` function at the module level
        # The `api_stop()` function is for backwards compatibility (will be deprecated)
        stop_fns = [f"{ext_id}_stop", "api_stop"]
        stop_fn_name = next((fn for fn in stop_fns if hasattr(old_module, fn)), None)
        assert stop_fn_name, "No stop function found for '{ext.module_name}'"

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
