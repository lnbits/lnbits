import importlib
import json
from pathlib import Path
from typing import List, Optional

import httpx
from loguru import logger

from lnbits.core.crud import delete_installed_extension, get_installed_extension
from lnbits.settings import settings

from .helpers import github_api_get
from .models import Extension, ExtensionConfig

# All subdirectories in the current directory, not recursive.


class ExtensionManager:
    def __init__(self) -> None:
        p = Path(settings.lnbits_extensions_path, "extensions")
        Path(p).mkdir(parents=True, exist_ok=True)
        self._extension_folders: List[Path] = [f for f in p.iterdir() if f.is_dir()]

    @property
    def extensions(self) -> List[Extension]:
        # todo: remove this property somehow, it is too expensive
        output: List[Extension] = []

        for extension_folder in self._extension_folders:
            extension_code = extension_folder.parts[-1]
            try:
                with open(extension_folder / "config.json") as json_file:
                    config = json.load(json_file)
                is_valid = True
                is_admin_only = extension_code in settings.lnbits_admin_extensions
            except Exception:
                config = {}
                is_valid = False
                is_admin_only = False

            output.append(
                Extension(
                    extension_code,
                    is_valid,
                    is_admin_only,
                    config.get("name"),
                    config.get("short_description"),
                    config.get("tile"),
                    config.get("contributors"),
                    config.get("hidden") or False,
                    config.get("migration_module"),
                    config.get("db_name"),
                )
            )

        return output


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


def get_valid_extensions(include_deactivated: Optional[bool] = True) -> List[Extension]:
    valid_extensions = [
        extension for extension in ExtensionManager().extensions if extension.is_valid
    ]

    if include_deactivated:
        return valid_extensions

    if settings.lnbits_extensions_deactivate_all:
        return []

    return [
        e
        for e in valid_extensions
        if e.code not in settings.lnbits_deactivated_extensions
    ]
