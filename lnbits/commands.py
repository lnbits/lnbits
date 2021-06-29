import trio
import warnings
import click
import importlib
import re
import os
from sqlalchemy.exc import OperationalError  # type: ignore

from .core import db as core_db, migrations as core_migrations
from .helpers import (
    get_valid_extensions,
    get_css_vendored,
    get_js_vendored,
    url_for_vendored,
)
from .settings import LNBITS_PATH


@click.command("migrate")
def db_migrate():
    trio.run(migrate_databases)


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
        try:
            rows = await (await conn.execute("SELECT * FROM dbversions")).fetchall()
        except OperationalError:
            # migration 3 wasn't ran
            await core_migrations.m000_create_migrations_table(conn)
            rows = await (await conn.execute("SELECT * FROM dbversions")).fetchall()

        current_versions = {row["db"]: row["version"] for row in rows}
        matcher = re.compile(r"^m(\d\d\d)_")

        async def run_migration(db, migrations_module):
            db_name = migrations_module.__name__.split(".")[-2]
            for key, migrate in migrations_module.__dict__.items():
                match = match = matcher.match(key)
                if match:
                    version = int(match.group(1))
                    if version > current_versions.get(db_name, 0):
                        print(f"running migration {db_name}.{version}")
                        await migrate(db)
                        await conn.execute(
                            "INSERT OR REPLACE INTO dbversions (db, version) VALUES (?, ?)",
                            (db_name, version),
                        )

        await run_migration(conn, core_migrations)

        for ext in get_valid_extensions():
            try:
                ext_migrations = importlib.import_module(
                    f"lnbits.extensions.{ext.code}.migrations"
                )
                ext_db = importlib.import_module(f"lnbits.extensions.{ext.code}").db
                await run_migration(ext_db, ext_migrations)
            except ImportError:
                raise ImportError(
                    f"Please make sure that the extension `{ext.code}` has a migrations file."
                )
