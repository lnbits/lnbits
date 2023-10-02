# Python script to migrate an LNbits SQLite DB to Postgres
# All credits to @Fritz446 for the awesome work

# pip install psycopg2 OR psycopg2-binary

import argparse
import os
import sqlite3
import sys
from typing import List

import psycopg2

from lnbits.settings import settings

sqfolder = settings.lnbits_data_folder
db_url = settings.lnbits_database_url

if db_url is None:
    print("missing LNBITS_DATABASE_URL")
    sys.exit(1)
else:
    # parse postgres://lnbits:postgres@localhost:5432/lnbits
    pgdb = db_url.split("/")[-1]
    pguser = db_url.split("@")[0].split(":")[-2][2:]
    pgpswd = db_url.split("@")[0].split(":")[-1]
    pghost = db_url.split("@")[1].split(":")[0]
    pgport = db_url.split("@")[1].split(":")[1].split("/")[0]
    pgschema = ""


def get_sqlite_cursor(sqdb):
    consq = sqlite3.connect(sqdb)
    return consq.cursor()


def get_postgres_cursor():
    conpg = psycopg2.connect(
        database=pgdb, user=pguser, password=pgpswd, host=pghost, port=pgport
    )
    return conpg.cursor()


def check_db_versions(sqdb):
    sqlite = get_sqlite_cursor(sqdb)
    dblite = dict(sqlite.execute("SELECT * FROM dbversions;").fetchall())
    sqlite.close()

    postgres = get_postgres_cursor()
    postgres.execute("SELECT * FROM public.dbversions;")
    dbpost = dict(postgres.fetchall())

    for key, value in dblite.items():
        if key in dblite and key in dbpost:
            version = dbpost[key]
            if value != version:
                raise Exception(
                    f"sqlite database version ({value}) of {key} doesn't match postgres"
                    f" database version {version}"
                )

    connection = postgres.connection
    postgres.close()
    connection.close()

    print("Database versions OK, converting")


def fix_id(seq, values):
    if not values or len(values) == 0:
        return

    postgres = get_postgres_cursor()

    max_id = values[len(values) - 1][0]
    postgres.execute(f"SELECT setval('{seq}', {max_id});")

    connection = postgres.connection
    postgres.close()
    connection.close()


def insert_to_pg(query, data):
    if len(data) == 0:
        return

    cursor = get_postgres_cursor()
    connection = cursor.connection

    for d in data:
        try:
            cursor.execute(query, d)
        except Exception as e:
            if args.ignore_errors:
                print(e)
                print(f"Failed to insert {d}")
            else:
                print("query:", query)
                print("data:", d)
                raise ValueError(f"Failed to insert {d}")
    connection.commit()

    cursor.close()
    connection.close()


def migrate_core(file: str, exclude_tables: List[str] = None):
    print(f"Migrating core: {file}")
    migrate_db(file, "public", exclude_tables)
    print("✅ Migrated core")


def migrate_ext(file: str):
    filename = os.path.basename(file)
    schema = filename.replace("ext_", "").split(".")[0]
    print(f"Migrating ext: {schema} from file {file}")
    migrate_db(file, schema)
    print(f"✅ Migrated ext: {schema}")


def migrate_db(file: str, schema: str, exclude_tables: List[str] = None):
    # first we check if this file exists:
    assert os.path.isfile(file), f"{file} does not exist!"

    sq = get_sqlite_cursor(file)
    tables = sq.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name not like 'sqlite?_%' escape '?'
    """
    ).fetchall()

    for table in tables:
        tableName = table[0]
        print(f"Migrating table {tableName}")
        # hard coded skip for dbversions (already produced during startup)
        if tableName == "dbversions":
            continue
        if exclude_tables and tableName in exclude_tables:
            continue

        columns = sq.execute(f"PRAGMA table_info({tableName})").fetchall()
        q = build_insert_query(schema, tableName, columns)

        data = sq.execute(f"SELECT * FROM {tableName};").fetchall()

        if len(data) == 0:
            print(f"🛑 You sneaky dev! Table {tableName} is empty!")

        insert_to_pg(q, data)
    sq.close()


def build_insert_query(schema, tableName, columns):
    to_columns = ", ".join(map(lambda column: f'"{column[1].lower()}"', columns))
    values = ", ".join(map(lambda column: to_column_type(column[2]), columns))
    return f"""
            INSERT INTO {schema}.{tableName}({to_columns})
            VALUES ({values});
        """


def to_column_type(columnType):
    if columnType == "TIMESTAMP":
        return "to_timestamp(%s)"
    if columnType in ["BOOLEAN", "BOOL"]:
        return "%s::boolean"
    return "%s"


parser = argparse.ArgumentParser(
    description="LNbits migration tool for migrating data from SQLite to PostgreSQL"
)
parser.add_argument(
    dest="sqlite_path",
    const=True,
    nargs="?",
    help=(
        "SQLite DB folder *or* single extension db file to migrate. Default:"
        f" {sqfolder}"
    ),
    default=sqfolder,
    type=str,
)
parser.add_argument(
    "-e",
    "--extensions-only",
    help="Migrate only extensions",
    required=False,
    default=False,
    action="store_true",
)

parser.add_argument(
    "-s",
    "--skip-missing",
    help="Error if migration is missing for an extension",
    required=False,
    default=False,
    action="store_true",
)

parser.add_argument(
    "-i",
    "--ignore-errors",
    help="Don't error if migration fails",
    required=False,
    default=False,
    action="store_true",
)

args = parser.parse_args()

print("Selected path: ", args.sqlite_path)

if os.path.isdir(args.sqlite_path):
    exclude_tables = ["dbversions"]
    file = os.path.join(args.sqlite_path, "database.sqlite3")
    check_db_versions(file)
    if not args.extensions_only:
        migrate_core(file, exclude_tables)

if os.path.isdir(args.sqlite_path):
    files = [
        os.path.join(args.sqlite_path, file) for file in os.listdir(args.sqlite_path)
    ]
else:
    files = [args.sqlite_path]


excluded_exts = ["ext_lnurlpos.sqlite3"]
for file in files:
    filename = os.path.basename(file)
    if filename.startswith("ext_") and filename not in excluded_exts:
        migrate_ext(file)
