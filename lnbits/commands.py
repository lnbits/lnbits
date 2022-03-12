import asyncio
import importlib
import os
import re
import warnings
from typing import Optional

import click
from genericpath import exists

from .core import db as core_db
from .core import migrations as core_migrations
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

async def get_admin_settings():
    from lnbits.extensions.admin.models import Admin

    async with core_db.connect() as conn:
        
        if conn.type == SQLITE:
            exists = await conn.fetchone(
                "SELECT * FROM sqlite_master WHERE type='table' AND name='admin'"
            )
        elif conn.type in {POSTGRES, COCKROACH}:
            exists = await conn.fetchone(
                "SELECT * FROM information_schema.tables WHERE table_name = 'admin'"
            )
        if not exists:
            return False

        row = await conn.fetchone("SELECT * from admin")
    
    return Admin(**row) if row else None

async def migrate_databases():
    """Creates the necessary databases if they don't exist already; or migrates them."""

    async def set_migration_version(conn, db_name, version):
        await conn.execute(
            """
            INSERT INTO dbversions (db, version) VALUES (?, ?)
            ON CONFLICT (db) DO UPDATE SET version = ?
            """,
            (db_name, version, version),
        )

    async def run_migration(db, migrations_module):
        db_name = migrations_module.__name__.split(".")[-2]
        for key, migrate in migrations_module.__dict__.items():
            match = match = matcher.match(key)
            if match:
                version = int(match.group(1))
                if version > current_versions.get(db_name, 0):
                    print(f"running migration {db_name}.{version}")
                    await migrate(db)

                    if db.schema == None:
                        await set_migration_version(db, db_name, version)
                    else:
                        async with core_db.connect() as conn:
                            await set_migration_version(conn, db_name, version)

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

        rows = await (await conn.execute("SELECT * FROM dbversions")).fetchall()
        current_versions = {row["db"]: row["version"] for row in rows}
        matcher = re.compile(r"^m(\d\d\d)_")
        await run_migration(conn, core_migrations)

    for ext in get_valid_extensions():
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
            await run_migration(ext_conn, ext_migrations)

    print("  ✔️ All migrations done.")
