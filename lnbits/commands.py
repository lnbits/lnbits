import asyncio
from pathlib import Path
from typing import Any, Optional

import click
import httpx
from loguru import logger
from packaging import version

from lnbits.core.models import User
from lnbits.core.services import check_admin_settings
from lnbits.core.views.api import api_install_extension, api_uninstall_extension
from lnbits.settings import settings

from .core import db as core_db
from .core import migrations as core_migrations
from .core.crud import (
    get_dbversions,
    get_inactive_extensions,
    get_installed_extension,
)
from .core.helpers import migrate_extension_database, run_migration
from .db import COCKROACH, POSTGRES, SQLITE
from .extension_manager import (
    CreateExtension,
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
@click.option("-a", "--all", is_flag=True, help="Upgrade all extensions.")
@click.argument("extension", required=False)
def extensions_upgrade(extension: Optional[str] = None, all: Optional[bool] = False):
    """Upgrade extensions"""
    if not extension and not all:
        click.echo("Extension ID is required.")
        click.echo("Or specify the '--all' flag to upgrade all extensions")
        return
    if extension and all:
        click.echo("Only one of extension ID or the '--all' flag must be specified")
        return

    if extension:
        click.echo(f"Updating {extension} extension.")

        async def wrap():
            await check_admin_settings()
            if await _is_lnbits_started():
                click.echo(
                    "Please stop LNbits before installing extensions from the CLI."
                )
                click.echo(
                    f"Extensions can be upgraded via the UI here: 'http://{settings.host}:{settings.port}/extensions'"
                )
                return
            await upgrade_extension(extension)

        _run_async(wrap)
        return
    click.echo("Updating all extensions...")


@extensions.command("install")
@click.argument("extension")
@click.option("--repo-index")
def extensions_install(extension: str, repo_index: Optional[str] = None):
    """Install a extension"""
    click.echo(f"Installing {extension}... {repo_index}")

    async def wrap():
        await check_admin_settings()
        if await _is_lnbits_started():
            click.echo("Please stop LNbits before installing extensions from the CLI.")
            click.echo(
                f"Extensions can be installed via the UI here: 'http://{settings.host}:{settings.port}/extensions'"
            )
            return
        await install_extension(extension, repo_index)
        # await api_install_extension()

    _run_async(wrap)


@extensions.command("uninstall")
@click.argument("extension")
def extensions_uninstall(extension: str):
    """Uninstall a extension"""
    click.echo(f"Uninstalling {extension}...")

    async def wrap():
        await check_admin_settings()
        if await _is_lnbits_started():
            click.echo(
                "Please stop LNbits before uninstalling extensions from the CLI."
            )
            click.echo(
                f"Extensions can be uninstalled via the UI here: 'http://{settings.host}:{settings.port}/extensions'"
            )
            return False
        await uninstall_extension(extension)

    _run_async(wrap)


def main():
    """main function"""
    lnbits_cli()


if __name__ == "__main__":
    main()


def _run_async(fn) -> Any:
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(fn())


async def install_extension(
    extension: str, repo_index: Optional[str] = None, source_repo: Optional[str] = None
) -> None:
    all_releases = await InstallableExtension.get_extension_releases(extension)
    if len(all_releases) == 0:
        click.echo(f"No repository found for extension '{extension}'.")
        return

    latest_repo_releases = _get_latest_release_per_repo(all_releases)

    if source_repo:
        if source_repo not in latest_repo_releases:
            click.echo(f"Repository not found: '{source_repo}'")
            return
        release = latest_repo_releases[source_repo]
    elif len(latest_repo_releases) == 1:
        release = latest_repo_releases[list(latest_repo_releases.keys())[0]]
    else:
        repos = list(latest_repo_releases.keys())
        repos.sort()
        if not repo_index:
            click.echo(f"Multiple repos found for extension '{extension}'.")
            click.echo("Please select your repo using the '--repo-index' flag")
            click.echo("Repositories: ")

            for index, repo in enumerate(repos):
                release = latest_repo_releases[repo]
                click.echo(f"  [{index}] {repo} --> {release.version}")
            return

        if not repo_index.isnumeric() or not 0 <= int(repo_index) < len(repos):
            click.echo(f"--repo-index must be between '0' and '{len(repos) - 1}'")
            return
        release = latest_repo_releases[repos[int(repo_index)]]

    data = CreateExtension(
        ext_id=extension, archive=release.archive, source_repo=release.source_repo
    )
    user = User(id=get_super_user(), super_user=True)
    await api_install_extension(data, user)
    click.echo(f"Extension '{extension}' installed.")


async def uninstall_extension(extension) -> bool:
    user = User(id=get_super_user(), super_user=True)
    await api_uninstall_extension(extension, user)

    click.echo(f"Extension '{extension}' uninstalled.")
    return True


async def upgrade_extension(extension):
    all_releases = await InstallableExtension.get_extension_releases(extension)
    if len(all_releases) == 0:
        click.echo(f"No repository found for extension '{extension}'.")
        return
    installed_ext = await get_installed_extension(extension)
    if not installed_ext:
        click.echo(f"Extension '{extension}' is not installed")
        click.echo(f"Please use the install command to install '{extension}.")
        return
    click.echo(
        f"Current '{extension}' extension version: {installed_ext.installed_version}"
    )
    latest_repo_releases = _get_latest_release_per_repo(all_releases)
    source_repo = installed_ext.installed_release.source_repo
    if source_repo in latest_repo_releases:
        latest_release = latest_repo_releases[source_repo]
        if latest_release.version == installed_ext.installed_version:
            click.echo(f"Extension '{extension}' already up to date.")
            return
        click.echo(
            f"Upgrading '{extension}' extension to version: {latest_release.version }"
        )
        uninstalled = await uninstall_extension(extension)
        if not uninstalled:
            return
        await install_extension(extension=extension, source_repo=source_repo)
        # print("### latest_release", latest_release)

    # print('### installed_ext', installed_ext)


def _get_latest_release_per_repo(all_releases):
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
    return latest_repo_releases


async def _is_lnbits_started():
    try:
        async with httpx.AsyncClient() as client:
            await client.get(f"http://{settings.host}:{settings.port}/api/v1/health")
            return True
    except:
        return False
