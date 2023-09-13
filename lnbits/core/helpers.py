import importlib
import re
from typing import Any
from uuid import UUID

import httpx
from loguru import logger

from lnbits.db import Connection
from lnbits.extension_manager import Extension
from lnbits.settings import settings

from . import db as core_db
from .crud import update_migration_version


async def migrate_extension_database(ext: Extension, current_version):
    try:
        ext_migrations = importlib.import_module(f"{ext.module_name}.migrations")
        ext_db = importlib.import_module(ext.module_name).db
    except ImportError as e:
        logger.error(e)
        raise ImportError(
            f"Please make sure that the extension `{ext.code}` has a migrations file."
        )

    async with ext_db.connect() as ext_conn:
        await run_migration(ext_conn, ext_migrations, current_version)


async def run_migration(db: Connection, migrations_module: Any, current_version: int):
    matcher = re.compile(r"^m(\d\d\d)_")
    db_name = migrations_module.__name__.split(".")[-2]
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


async def stop_extension_background_work(ext_id: str, user: str):
    """
    Stop background work for extension (like asyncio.Tasks, WebSockets, etc).
    Extensions SHOULD expose a DELETE enpoint at the root level of their API.
    This function tries first to call the endpoint using `http`
    and if it fails it tries using `https`.
    """
    async with httpx.AsyncClient() as client:
        try:
            url = f"http://{settings.host}:{settings.port}/{ext_id}/api/v1?usr={user}"
            await client.delete(url)
        except Exception as ex:
            logger.warning(ex)
            try:
                # try https
                url = f"https://{settings.host}:{settings.port}/{ext_id}/api/v1?usr={user}"
            except Exception as ex:
                logger.warning(ex)


def to_valid_user_id(user_id: str) -> UUID:
    if len(user_id) < 32:
        raise ValueError("User ID must have at least 128 bits")
    try:
        int(user_id, 16)
    except Exception:
        raise ValueError("Invalid hex string for User ID.")

    return UUID(hex=user_id[:32], version=4)
