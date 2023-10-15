import asyncio
from pathlib import Path

import click
from loguru import logger

from lnbits.settings import settings

from .core import db as core_db
from .core import migrations as core_migrations
from .core.crud import get_dbversions, get_inactive_extensions
from .core.helpers import migrate_extension_database, run_migration
from .db import COCKROACH, POSTGRES, SQLITE
from .extension_manager import get_valid_extensions


@click.group()
def lnbits_cli():
    """
    Python CLI for LNbits
    """


@lnbits_cli.group()
def db():
    """
    Database related commands
    """


def get_super_user() -> str:
    """Get the superuser"""
    with open(Path(settings.lnbits_data_folder) / ".super_user", "r") as file:
        return file.readline()


@lnbits_cli.command("superuser")
def superuser():
    """Prints the superuser"""
    click.echo(get_super_user())


@lnbits_cli.command("superuser-url")
def superuser_url():
    """Prints the superuser"""
    click.echo(f"http://{settings.host}:{settings.port}/wallet?usr={get_super_user()}")


@lnbits_cli.command("delete-settings")
def delete_settings():
    """Deletes the settings"""

    async def wrap():
        async with core_db.connect() as conn:
            await conn.execute("DELETE from settings")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(wrap())


@db.command("migrate")
def database_migrate():
    """Migrate databases"""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(migrate_databases())


async def db_migrate():
    asyncio.create_task(migrate_databases())


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
        await run_migration(conn, core_migrations, core_version)

    for ext in get_valid_extensions():
        current_version = current_versions.get(ext.code, 0)
        try:
            await migrate_extension_database(ext, current_version)
        except Exception as e:
            logger.exception(f"Error migrating extension {ext.code}: {e}")

    logger.info("✔️ All migrations done.")


@db.command("versions")
def database_versions():
    """Show current database versions"""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(db_versions())


async def db_versions():
    """Show current database versions"""
    async with core_db.connect() as conn:
        return await get_dbversions(conn)


async def load_disabled_extension_list() -> None:
    """Update list of extensions that have been explicitly disabled"""
    inactive_extensions = await get_inactive_extensions()
    settings.lnbits_deactivated_extensions += inactive_extensions


def main():
    """main function"""
    lnbits_cli()


if __name__ == "__main__":
    main()
