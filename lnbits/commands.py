import asyncio
from pathlib import Path
from typing import Any, Optional

import click
import httpx
from loguru import logger
from packaging import version

from lnbits.core.services import check_admin_settings
from lnbits.settings import settings

from .core import db as core_db
from .core import migrations as core_migrations
from .core.crud import (
    add_installed_extension,
    delete_installed_extension,
    get_dbversions,
    get_inactive_extensions,
    get_installed_extension,
)
from .core.helpers import migrate_extension_database, run_migration
from .db import COCKROACH, POSTGRES, SQLITE
from .extension_manager import (
    InstallableExtension,
    get_valid_extensions,
)


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


@lnbits_cli.group()
def extensions():
    """
    Extensions related commands
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


@extensions.command("list")
def extensions_list():
    """Show currently installed extensions"""
    click.echo("Installed extensions:")

    async def wrap():
        from lnbits.app import build_all_installed_extensions_list

        for ext in await build_all_installed_extensions_list():
            assert ext.installed_release, f"Extension {ext.id} has no installed_release"
            click.echo(f"  - {ext.id} ({ext.installed_release.version})")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(wrap())


@extensions.command("upgrade")
def extensions_upgrade():
    """Update all extension"""
    click.echo("Updating all extensions...")


@extensions.command("update")
@click.argument("extension")
def extensions_update(extension: str):
    """Update a extension"""
    click.echo(f"Updating {extension}...")


@extensions.command("install")
@click.argument("extension")
@click.option("--repo-index")
def extensions_install(extension: str, repo_index: Optional[str] = None):
    """Install a extension"""
    click.echo(f"Installing {extension}... {repo_index}")

    async def wrap() -> None:
        await check_admin_settings()
        if await _is_lnbits_started():
            click.echo("Please stop LNbits before installing extensions from the CLI.")
            click.echo(
                f"Extensions can be installed via the UI here: 'http://{settings.host}:{settings.port}/extensions'"
            )
            return

        installed_ext = await get_installed_extension(extension)
        if installed_ext:
            click.echo(
                f"Extension '{extension}' already installed. Version: "
                + f" {installed_ext.installed_version}."
            )
            click.echo("Please use the 'upgrade' command.")
            return

        all_releases = await InstallableExtension.get_extension_releases(extension)
        if len(all_releases) == 0:
            click.echo(f"No repository found for extension '{extension}'.")
            return

        latest_repo_releases = {}
        for release in all_releases:
            if not release.is_version_compatible:
                continue
            if release.source_repo not in latest_repo_releases:
                latest_repo_releases[release.source_repo] = release
                continue
            if version.parse(release.version) > version.parse(
                latest_repo_releases[release.source_repo].version
            ):
                latest_repo_releases[release.source_repo] = release

        if len(latest_repo_releases) == 1:
            release = latest_repo_releases[list(latest_repo_releases.keys())[0]]
            ext_info = InstallableExtension(
                id=extension,
                name=extension,
                installed_release=release,
                icon=release.icon,
            )

            await add_installed_extension(ext_info)
            return

        repos = list(latest_repo_releases.keys())
        repos.sort()
        if not repo_index:
            click.echo(
                f"Extension '{extension}' is present in more than one repository."
            )
            click.echo("Please select your repo using the '--repo-index' flag")
            click.echo("Repositories: ")

            for index, repo in enumerate(repos):
                release = latest_repo_releases[repo]
                click.echo(f"  [{index}] {repo} --> {release.version}")
            return

        if (
            not repo_index.isnumeric()
            or int(repo_index) < 0
            or int(repo_index) >= len(repos)
        ):
            click.echo(
                f"--repo-index option must be an int between '0' and '{len(repos) - 1}'"
            )
            return
        release = latest_repo_releases[repos[int(repo_index)]]
        ext_info = InstallableExtension(
            id=extension, name=extension, installed_release=release, icon=release.icon
        )
        await add_installed_extension(ext_info)
        click.echo(
            f"Extension '{extension}' added."
            + " It will be automatically installed when LNbits starts."
        )

    _run_async(wrap)


@extensions.command("uninstall")
@click.argument("extension")
def extensions_uninstall(extension: str):
    """Uninstall a extension"""
    click.echo(f"Uninstalling {extension}...")

    async def wrap() -> None:
        await check_admin_settings()
        if await _is_lnbits_started():
            click.echo(
                "Please stop LNbits before uninstalling extensions from the CLI."
            )
            click.echo(
                f"Extensions can be uninstalled via the UI here: 'http://{settings.host}:{settings.port}/extensions'"
            )
            return

        installed_ext = await get_installed_extension(extension)
        if not installed_ext:
            click.echo(f"Extension '{extension}' is not installed")
            return

        installable_extensions = await InstallableExtension.get_installable_extensions()
        # check that other extensions do not depend on this one
        for valid_ext_id in list(map(lambda e: e.code, get_valid_extensions())):
            installed_ext = next(
                (ext for ext in installable_extensions if ext.id == valid_ext_id), None
            )
            if installed_ext and extension in installed_ext.dependencies:
                click.echo("Cannot uninstall.")
                click.echo(f"Extension '{installed_ext.name}' depends on this one.")

        extensions = [e for e in installable_extensions if e.id == extension]
        for ext_info in extensions:
            ext_info.clean_extension_files()
            await delete_installed_extension(ext_id=ext_info.id)

        click.echo(f"Extension '{extension}' uninstalled.")

    _run_async(wrap)


def main():
    """main function"""
    lnbits_cli()


if __name__ == "__main__":
    main()


def _run_async(fn) -> Any:
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(fn())


async def _is_lnbits_started():
    try:
        async with httpx.AsyncClient() as client:
            await client.get(f"http://{settings.host}:{settings.port}/api/v1/health")
            return True
    except:
        return False
