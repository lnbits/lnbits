import argparse
import os
import sqlite3
from typing import List

import psycopg2
from environs import Env  # type: ignore

env = Env()
env.read_env()

# Python script to migrate an LNbits SQLite DB to Postgres
# All credits to @Fritz446 for the awesome work


# pip install psycopg2 OR psycopg2-binary


# Change these values as needed


sqfolder = "data/"

LNBITS_DATABASE_URL = env.str("LNBITS_DATABASE_URL", default=None)
if LNBITS_DATABASE_URL is None:
    pgdb = "lnbits"
    pguser = "lnbits"
    pgpswd = "postgres"
    pghost = "localhost"
    pgport = "5432"
    pgschema = ""
else:
    # parse postgres://lnbits:postgres@localhost:5432/lnbits
    pgdb = LNBITS_DATABASE_URL.split("/")[-1]
    pguser = LNBITS_DATABASE_URL.split("@")[0].split(":")[-2][2:]
    pgpswd = LNBITS_DATABASE_URL.split("@")[0].split(":")[-1]
    pghost = LNBITS_DATABASE_URL.split("@")[1].split(":")[0]
    pgport = LNBITS_DATABASE_URL.split("@")[1].split(":")[1].split("/")[0]
    pgschema = ""


def get_sqlite_cursor(sqdb) -> sqlite3:
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

    for key in dblite.keys():
        if key in dblite and key in dbpost and dblite[key] != dbpost[key]:
            raise Exception(
                f"sqlite database version ({dblite[key]}) of {key} doesn't match postgres database version {dbpost[key]}"
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


def migrate_core(file: str, exclude_tables: List[str] = []):
    print(f"Migrating core: {file}")
    migrate_db(file, "public", exclude_tables)
    print("✅ Migrated core")


def migrate_ext(file: str):
    filename = os.path.basename(file)
    schema = filename.replace("ext_", "").split(".")[0]
    print(f"Migrating ext: {file}.{schema}")
    migrate_db(file, schema)
    print(f"✅ Migrated ext: {schema}")


def migrate_db(file: str, schema: str, exclude_tables: List[str] = []):
    sq = get_sqlite_cursor(file)
    tables = sq.execute(
        """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name not like 'sqlite?_%' escape '?'
    """
    ).fetchall()

    for table in tables:
        tableName = table[0]
        if tableName in exclude_tables:
            continue

        columns = sq.execute(f"PRAGMA table_info({tableName})").fetchall()
        q = build_insert_query(schema, tableName, columns)

        data = sq.execute(f"SELECT * FROM {tableName};").fetchall()
        insert_to_pg(q, data)
    sq.close()


def build_insert_query(schema, tableName, columns):
    to_columns = ", ".join(map(lambda column: f'"{column[1]}"', columns))
    values = ", ".join(map(lambda column: to_column_type(column[2]), columns))
    return f"""
            INSERT INTO {schema}.{tableName}({to_columns})
            VALUES ({values});
        """


def to_column_type(columnType):
    if columnType == "TIMESTAMP":
        return "to_timestamp(%s)"
    if columnType == "BOOLEAN":
        return "%s::boolean"
    return "%s"


parser = argparse.ArgumentParser(
    description="LNbits migration tool for migrating data from SQLite to PostgreSQL"
)
parser.add_argument(
    dest="sqlite_path",
    const=True,
    nargs="?",
    help=f"SQLite DB folder *or* single extension db file to migrate. Default: {sqfolder}",
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
