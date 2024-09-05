import importlib
from typing import Optional

import httpx
from loguru import logger

from lnbits.core.crud import delete_installed_extension, get_installed_extension
from lnbits.settings import settings

from .helpers import github_api_get
from .models import Extension, ExtensionConfig

# All subdirectories in the current directory, not recursive.


async def fetch_github_release_config(
    org: str, repo: str, tag_name: str
) -> Optional[ExtensionConfig]:
    config_url = (
        f"https://raw.githubusercontent.com/{org}/{repo}/{tag_name}/config.json"
    )
    error_msg = "Cannot fetch GitHub extension config"
    config = await github_api_get(config_url, error_msg)
    return ExtensionConfig.parse_obj(config)


async def fetch_release_details(details_link: str) -> Optional[dict]:

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(details_link)
            resp.raise_for_status()
            data = resp.json()
            if "description_md" in data:
                resp = await client.get(data["description_md"])
                if not resp.is_error:
                    data["description_md"] = resp.text

            return data
    except Exception as e:
        logger.warning(e)
        return None


async def uninstall_extension(ext_id):
    await stop_extension_background_work(ext_id)

    settings.lnbits_deactivated_extensions.add(ext_id)

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
            await stop_fn()

        logger.info(f"Stopped background work for extension '{ext.module_name}'.")
    except Exception as ex:
        logger.warning(f"Failed to stop background work for '{ext.module_name}'.")
        logger.warning(ex)
        return False

    return True
