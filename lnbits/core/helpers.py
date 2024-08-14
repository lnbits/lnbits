import importlib
import re
from typing import Any, Optional
from uuid import UUID

import httpx
from loguru import logger

from lnbits.core import migrations as core_migrations
from lnbits.core.crud import (
    get_dbversions,
    get_installed_extensions,
    update_migration_version,
)
from lnbits.core.db import db as core_db
from lnbits.db import COCKROACH, POSTGRES, SQLITE, Connection
from lnbits.extension_manager import (
    Extension,
    get_valid_extensions,
)
from lnbits.settings import settings


async def migrate_extension_database(ext: Extension, current_version):
    try:
        ext_migrations = importlib.import_module(f"{ext.module_name}.migrations")
        ext_db = importlib.import_module(ext.module_name).db
    except ImportError as exc:
        logger.error(exc)
        raise ImportError(
            f"Please make sure that the extension `{ext.code}` has a migrations file."
        ) from exc

    async with ext_db.connect() as ext_conn:
        await run_migration(ext_conn, ext_migrations, ext.code, current_version)


async def run_migration(
    db: Connection, migrations_module: Any, db_name: str, current_version: int
):
    matcher = re.compile(r"^m(\d\d\d)_")
    for key, migrate in migrations_module.__dict__.items():
        match = matcher.match(key)
        if match:
            version = int(match.group(1))
            if version > current_version:
                logger.debug(f"running migration {db_name}.{version}")
                print(f"running migration {db_name}.{version}")
                await migrate(db)

                if db.schema is None:
                    await update_migration_version(db, db_name, version)
                else:
                    async with core_db.connect() as conn:
                        await update_migration_version(conn, db_name, version)


async def stop_extension_background_work(
    ext_id: str, user: str, access_token: Optional[str] = None
):
    """
    Stop background work for extension (like asyncio.Tasks, WebSockets, etc).
    Extensions SHOULD expose a `api_stop()` function and/or a DELETE enpoint
    at the root level of their API.
    """
    stopped = await _stop_extension_background_work(ext_id)

    if not stopped:
        # fallback to REST API call
        await _stop_extension_background_work_via_api(ext_id, user, access_token)


async def _stop_extension_background_work(ext_id) -> bool:
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


async def _stop_extension_background_work_via_api(ext_id, user, access_token):
    logger.info(
        f"Stopping background work for extension '{ext_id}' using the REST API."
    )
    async with httpx.AsyncClient() as client:
        try:
            url = f"http://{settings.host}:{settings.port}/{ext_id}/api/v1?usr={user}"
            headers = (
                {"Authorization": "Bearer " + access_token} if access_token else None
            )
            resp = await client.delete(url=url, headers=headers)
            resp.raise_for_status()
            logger.info(f"Stopped background work for extension '{ext_id}'.")
        except Exception as ex:
            logger.warning(
                f"Failed to stop background work for '{ext_id}' using the REST API."
            )
            logger.warning(ex)


def to_valid_user_id(user_id: str) -> UUID:
    if len(user_id) < 32:
        raise ValueError("User ID must have at least 128 bits")
    try:
        int(user_id, 16)
    except Exception as exc:
        raise ValueError("Invalid hex string for User ID.") from exc

    return UUID(hex=user_id[:32], version=4)


async def load_disabled_extension_list() -> None:
    """Update list of extensions that have been explicitly disabled"""
    inactive_extensions = await get_installed_extensions(active=False)
    settings.lnbits_deactivated_extensions.update([e.id for e in inactive_extensions])


async def migrate_databases():
    """Creates the necessary databases if they don't exist already; or migrates them."""

    async with core_db.connect() as conn:
        exists = False
        if conn.type == SQLITE:
            exists = await conn.fetchone(
                "SELECT * FROM sqlite_master WHERE type='table' AND name='dbversions'"
            )
        elif conn.type in {POSTGRES, COCKROACH}:
            exists = await conn.fetchone(
                "SELECT * FROM information_schema.tables WHERE table_schema = 'public'"
                " AND table_name = 'dbversions'"
            )

        if not exists:
            await core_migrations.m000_create_migrations_table(conn)

        current_versions = await get_dbversions(conn)
        core_version = current_versions.get("core", 0)
        await run_migration(conn, core_migrations, "core", core_version)

    # here is the first place we can be sure that the
    # `installed_extensions` table has been created
    await load_disabled_extension_list()

    # todo: revisit, use installed extensions
    for ext in get_valid_extensions(False):
        current_version = current_versions.get(ext.code, 0)
        try:
            await migrate_extension_database(ext, current_version)
        except Exception as e:
            logger.exception(f"Error migrating extension {ext.code}: {e}")

    logger.info("✔️ All migrations done.")
