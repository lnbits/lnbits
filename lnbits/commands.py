import asyncio
import importlib
import os
import re
import warnings

import click
from loguru import logger



from .core import db as core_db
from .core import migrations as core_migrations
from .core.crud import get_dbversions, update_migration_version

from .db import COCKROACH, POSTGRES, SQLITE
from .helpers import (
    get_css_vendored,
    get_js_vendored,
    get_valid_extensions,
    url_for_vendored,
)
from .settings import LNBITS_PATH


@click.command("migrate")
def db_migrate():
    asyncio.create_task(migrate_databases())


@click.command("assets")
def handle_assets():
    transpile_scss()
    bundle_vendored()


def transpile_scss():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from scss.compiler import compile_string  # type: ignore

        with open(os.path.join(LNBITS_PATH, "static/scss/base.scss")) as scss:
            with open(os.path.join(LNBITS_PATH, "static/css/base.css"), "w") as css:
                css.write(compile_string(scss.read()))


def bundle_vendored():
    for getfiles, outputpath in [
        (get_js_vendored, os.path.join(LNBITS_PATH, "static/bundle.js")),
        (get_css_vendored, os.path.join(LNBITS_PATH, "static/bundle.css")),
    ]:
        output = ""
        for path in getfiles():
            with open(path) as f:
                output += "/* " + url_for_vendored(path) + " */\n" + f.read() + ";\n"
        with open(outputpath, "w") as f:
            f.write(output)


async def migrate_databases():
    """Creates the necessary databases if they don't exist already; or migrates them."""

    async with core_db.connect() as conn:
        if conn.type == SQLITE:
            exists = await conn.fetchone(
                "SELECT * FROM sqlite_master WHERE type='table' AND name='dbversions'"
            )
        elif conn.type in {POSTGRES, COCKROACH}:
            exists = await conn.fetchone(
                "SELECT * FROM information_schema.tables WHERE table_name = 'dbversions'"
            )

        if not exists:
            await core_migrations.m000_create_migrations_table(conn)

        current_versions = await get_dbversions(conn)
        core_version =  current_versions.get("core", 0)
        await _run_migration(conn, core_migrations, core_version)

    for ext in get_valid_extensions():
       current_version =  current_versions.get(ext.code, 0)
       await  migrate_extension_database(ext, current_version)

    logger.info("✔️ All migrations done.")

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
        await _run_migration(ext_conn, ext_migrations, current_version)

async def _run_migration(db, migrations_module, current_version):
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
