import asyncio
import os
import warnings
from copy import deepcopy
from pathlib import Path

import click
import toml
from loguru import logger

from lnbits.settings import settings

from .core import db as core_db
from .core import migrations as core_migrations
from .core.crud import get_dbversions, get_inactive_extensions
from .core.helpers import migrate_extension_database, run_migration, run_process
from .db import COCKROACH, POSTGRES, SQLITE
from .extension_manager import ExtensionInstallationException, get_valid_extensions


@click.group()
def cli():
    pass


@cli.command("migrate")
def db_migrate():
    asyncio.run(migrate_core_databases())
    asyncio.run(migrate_extensions_databases())


@cli.command("assets")
def handle_assets():
    transpile_scss()


@cli.command("update")
def update_extensions():
    asyncio.run(check_extension_dependencies())


def transpile_scss():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from scss.compiler import compile_string  # type: ignore

        with open(os.path.join(settings.lnbits_path, "static/scss/base.scss")) as scss:
            with open(
                os.path.join(settings.lnbits_path, "static/css/base.css"), "w"
            ) as css:
                css.write(compile_string(scss.read()))


async def migrate_core_databases():
    """Creates the necessary databases if they don't exist already; or migrates them."""

    async with core_db.connect() as conn:
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

    logger.info("✔️ Core migrations done.")


async def migrate_extensions_databases():
    current_versions = await get_dbversions()

    for ext in get_valid_extensions():
        current_version = current_versions.get(ext.code, 0)
        await migrate_extension_database(ext, current_version)

    logger.info("✔️ Extensions migrations done.")


async def check_extension_dependencies():
    """Makes sure that dependencies of extensions are installed"""

    ext_pyproject_path = os.path.join("lnbits", "extensions", "pyproject.toml")

    pyproject = toml.load(ext_pyproject_path)
    pyproject_modified = deepcopy(pyproject)

    modified_deps = pyproject_modified["tool"]["poetry"]["dependencies"] = {}

    for ext in get_valid_extensions():
        ext_dir = os.path.join("lnbits", "extensions", ext.code)
        if Path(ext_dir, "pyproject.toml").is_file():
            modified_deps[ext.code] = {"path": ext.code, "develop": True}
    try:
        original = set(pyproject["tool"]["poetry"]["dependencies"].keys())
    except KeyError:
        original = set()
    modified = set(modified_deps.keys())

    additions = modified.difference(original)
    removals = original.difference(modified)

    if additions or removals:

        if not settings.lnbits_poetry_path:
            raise ExtensionInstallationException(
                "You must use poetry to install extensions with dependencies"
            )

        logger.info("Detected changes in extensions")
        if additions:
            logger.info(f"Adding: {additions}")
        if removals:
            logger.info(f"Removing: {removals} ")
        with open(ext_pyproject_path, "w") as toml_file:
            toml.dump(pyproject_modified, toml_file)
        try:
            await run_process(settings.lnbits_poetry_path, "lock")
            # When lnbits_poetry_sync is set, install should always run, regardless
            # of the actions done. Otherwise, only run install when new packages are added.
            if settings.lnbits_poetry_sync:
                await run_process(
                    settings.lnbits_poetry_path, "install", "--no-root", "--sync"
                )
            elif additions:
                await run_process(settings.lnbits_poetry_path, "install", "--no-root")
        except (FileNotFoundError, ValueError) as ex:
            # When something goes wrong, backup
            logger.error("Could not update.")
            with open(ext_pyproject_path, "w") as toml_file:
                toml.dump(pyproject, toml_file)
            if isinstance(ex, FileNotFoundError):
                msg = "You must use poetry to install extensions with dependencies"
            else:
                msg = "Dependencies could not be installed. Please check for any collisions"
            raise ExtensionInstallationException(msg)

    logger.info("✔️ All dependencies installed.")


async def db_versions():
    async with core_db.connect() as conn:
        current_versions = await get_dbversions(conn)
        return current_versions


async def load_disabled_extension_list() -> None:
    """Update list of extensions that have been explicitly disabled"""
    inactive_extensions = await get_inactive_extensions()
    settings.lnbits_deactivated_extensions += inactive_extensions


if __name__ == "__main__":
    cli()
