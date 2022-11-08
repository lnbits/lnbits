import importlib
import re

from loguru import logger

from . import db as core_db
from .crud import update_migration_version


async def migrate_extension_database(ext, current_version):
    try:
        ext_migrations = importlib.import_module(
            f"lnbits.extensions.{ext.code}.migrations"
        )
        ext_db = importlib.import_module(f"lnbits.extensions.{ext.code}").db
    except ImportError:
        raise ImportError(
            f"Please make sure that the extension `{ext.code}` has a migrations file."
        )

    async with ext_db.connect() as ext_conn:
        await run_migration(ext_conn, ext_migrations, current_version)


async def run_migration(db, migrations_module, current_version):
    matcher = re.compile(r"^m(\d\d\d)_")
    db_name = migrations_module.__name__.split(".")[-2]
    for key, migrate in migrations_module.__dict__.items():
        match = match = matcher.match(key)
        if match:
            version = int(match.group(1))
            if version > current_version:
                logger.debug(f"running migration {db_name}.{version}")
                print(f"running migration {db_name}.{version}")
                await migrate(db)

                if db.schema == None:
                    await update_migration_version(db, db_name, version)
                else:
                    async with core_db.connect() as conn:
                        await update_migration_version(conn, db_name, version)
