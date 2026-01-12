# Python script to migrate an LNbits SQLite DB to Postgres
# credits to @Fritz446 for the awesome work

# pip install psycopg2 OR psycopg2-binary

import argparse
import os
import sqlite3
import sys

from loguru import logger

from lnbits.settings import settings

try:
    import psycopg2  # type: ignore
except ImportError:
    logger.warning("Please install psycopg2")
    sys.exit(1)

sqfolder = settings.lnbits_data_folder
db_url = settings.lnbits_database_url

if db_url is None:
    logger.warning("missing LNBITS_DATABASE_URL")
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
    dbpost = dict(postgres.fetchall())  # type: ignore

    for key, value in dblite.items():
        if key in dblite and key in dbpost:
            version = dbpost[key]
            if value != version:
                raise Exception(
                    f"sqlite database version ({value}) of {key} doesn't match "
                    f"postgres database version {version}"
                )

    connection = postgres.connection
    postgres.close()
    connection.close()

    logger.info("Database versions OK, converting")


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
        except Exception as exc:
            if args.ignore_errors:
                logger.error(exc)
                logger.error(f"Failed to insert {d}")
            else:
                logger.error("query:", query)
                logger.error("data:", d)
                raise ValueError(f"Failed to insert {d}") from exc
    connection.commit()

    cursor.close()
    connection.close()


def migrate_core(file: str, exclude_tables: list[str] | None = None):
    if exclude_tables is None:
        exclude_tables = []
    logger.info(f"Migrating core: {file}")
    migrate_db(file, "public", exclude_tables)
    logger.info("✅ Migrated core")


def migrate_ext(file: str):
    filename = os.path.basename(file)
    schema = filename.replace("ext_", "").split(".")[0]
    try:
        logger.info(f"Migrating ext: {schema} from file {file}")
        migrate_db(file, schema)
        logger.info(f"✅ Migrated ext: {schema}")
    except Exception as exc:
        logger.error(f"🛑  Failed to migrate extension {schema}: {exc}")


def migrate_db(file: str, schema: str, exclude_tables: list[str] | None = None):
    # first we check if this file exists:
    if exclude_tables is None:
        exclude_tables = []
    assert os.path.isfile(file), f"{file} does not exist!"

    cursor = get_sqlite_cursor(file)
    tables = cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name not like 'sqlite?_%' escape '?'
    """
    ).fetchall()

    for table in tables:
        table_name = table[0]
        logger.info(f"Migrating table {table_name}")
        # hard coded skip for dbversions (already produced during startup)
        if table_name == "dbversions":
            continue
        if exclude_tables and table_name in exclude_tables:
            continue

        columns = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        q = build_insert_query(schema, table_name, columns)

        data = cursor.execute(f"SELECT * FROM {table_name};").fetchall()

        if len(data) == 0:
            logger.warning(f"🛑 You sneaky dev! Table {table_name} is empty!")

        insert_to_pg(q, data)
    cursor.close()


def build_insert_query(schema, table_name, columns):
    to_columns = ", ".join([f'"{column[1].lower()}"' for column in columns])
    values = ", ".join([to_column_type(column[2]) for column in columns])
    on_conflict_update = build_on_conflict_query_statement(schema, table_name, columns)
    return f"""
            INSERT INTO {schema}.{table_name}({to_columns})
            VALUES ({values})
            {on_conflict_update}
        """


def build_on_conflict_query_statement(schema, table_name, columns):
    unique_cols = table_unique_columns(schema, table_name)
    if len(unique_cols) == 0:
        return ""
    return f"""
        ON CONFLICT ({", ".join([f'"{col}"' for col in unique_cols])})
        DO UPDATE SET
        {", ".join([
            f'"{column[1].lower()}"=EXCLUDED."{column[1].lower()}"'
            for column in columns
            ])}
    """


def table_unique_columns(schema, table_name):
    cursor = get_postgres_cursor()
    query = f"""
        SELECT a.attname
        FROM   pg_index i
        JOIN   pg_attribute a ON a.attrelid = i.indrelid
                             AND a.attnum = ANY(i.indkey)
        WHERE  i.indrelid = '{schema}.{table_name}'::regclass
        AND    i.indisunique;
    """
    cursor.execute(query)
    columns = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return columns


def to_column_type(column_type):
    if column_type == "TIMESTAMP":
        return "to_timestamp(%s)"
    if column_type in ["BOOLEAN", "BOOL"]:
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

logger.info("Selected path: ", args.sqlite_path)

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
