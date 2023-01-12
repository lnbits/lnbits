import asyncio
import os
import warnings

import click
from loguru import logger

from lnbits.settings import settings

from .core import db as core_db
from .core import migrations as core_migrations
from .core.crud import get_dbversions, get_inactive_extensions
from .core.helpers import migrate_extension_database, run_migration
from .db import COCKROACH, POSTGRES, SQLITE
from .extension_manager import get_valid_extensions
from .helpers import get_css_vendored, get_js_vendored, url_for_vendored


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

        with open(os.path.join(settings.lnbits_path, "static/scss/base.scss")) as scss:
            with open(
                os.path.join(settings.lnbits_path, "static/css/base.css"), "w"
            ) as css:
                css.write(compile_string(scss.read()))


def bundle_vendored():
    for getfiles, outputpath in [
        (get_js_vendored, os.path.join(settings.lnbits_path, "static/bundle.js")),
        (get_css_vendored, os.path.join(settings.lnbits_path, "static/bundle.css")),
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
        exists = False
        if conn.type == SQLITE:
            exists = await conn.fetchone(
                "SELECT * FROM sqlite_master WHERE type='table' AND name='dbversions'"
            )
        elif conn.type in {POSTGRES, COCKROACH}:
            exists = await conn.fetchone(
                "SELECT * FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'dbversions'"
            )

        if not exists:
            await core_migrations.m000_create_migrations_table(conn)

        current_versions = await get_dbversions(conn)
        core_version = current_versions.get("core", 0)
        await run_migration(conn, core_migrations, core_version)

    for ext in get_valid_extensions():
        current_version = current_versions.get(ext.code, 0)
        await migrate_extension_database(ext, current_version)

    logger.info("✔️ All migrations done.")


async def db_versions():
    async with core_db.connect() as conn:
        current_versions = await get_dbversions(conn)
        return current_versions


async def load_disabled_extension_list() -> None:
    """Update list of extensions that have been explicitly disabled"""
    inactive_extensions = await get_inactive_extensions()
    settings.lnbits_deactivated_extensions += inactive_extensions
