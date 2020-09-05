import click
import importlib
import re
import sqlite3

from .core import migrations as core_migrations
from .db import open_db, open_ext_db
from .helpers import get_valid_extensions


@click.command("migrate")
def flask_migrate():
    migrate_databases()


def migrate_databases():
    """Creates the necessary databases if they don't exist already; or migrates them."""

    with open_db() as core_db:
        try:
            rows = core_db.fetchall("SELECT * FROM dbversions")
        except sqlite3.OperationalError:
            # migration 3 wasn't ran
            core_migrations.m000_create_migrations_table(core_db)
            rows = core_db.fetchall("SELECT * FROM dbversions")

        current_versions = {row["db"]: row["version"] for row in rows}
        matcher = re.compile(r"^m(\d\d\d)_")

        def run_migration(db, migrations_module):
            db_name = migrations_module.__name__.split(".")[-2]
            for key, run_migration in migrations_module.__dict__.items():
                match = match = matcher.match(key)
                if match:
                    version = int(match.group(1))
                    if version > current_versions.get(db_name, 0):
                        print(f"running migration {db_name}.{version}")
                        run_migration(db)
                        core_db.execute(
                            "INSERT OR REPLACE INTO dbversions (db, version) VALUES (?, ?)", (db_name, version)
                        )

        run_migration(core_db, core_migrations)

        for ext in get_valid_extensions():
            try:
                ext_migrations = importlib.import_module(f"lnbits.extensions.{ext.code}.migrations")
                with open_ext_db(ext.code) as db:
                    run_migration(db, ext_migrations)
            except ImportError:
                raise ImportError(f"Please make sure that the extension `{ext.code}` has a migrations file.")
