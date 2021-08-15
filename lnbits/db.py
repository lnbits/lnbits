import os
import trio
import time
import datetime
from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy import create_engine  # type: ignore
from sqlalchemy_aio import TRIO_STRATEGY  # type: ignore
from sqlalchemy_aio.base import AsyncConnection  # type: ignore

from .settings import LNBITS_DATA_FOLDER, LNBITS_DATABASE_URL

POSTGRES = "POSTGRES"
COCKROACH = "COCKROACH"
SQLITE = "SQLITE"


class Compat:
    type: Optional[str] = "<inherited>"
    schema: Optional[str] = "<inherited>"

    def interval_seconds(self, seconds: int) -> str:
        if self.type in {POSTGRES, COCKROACH}:
            return f"interval '{seconds} seconds'"
        elif self.type == SQLITE:
            return f"{seconds}"
        return "<nothing>"

    @property
    def timestamp_now(self) -> str:
        if self.type in {POSTGRES, COCKROACH}:
            return "now()"
        elif self.type == SQLITE:
            return "(strftime('%s', 'now'))"
        return "<nothing>"

    @property
    def serial_primary_key(self) -> str:
        if self.type in {POSTGRES, COCKROACH}:
            return "SERIAL PRIMARY KEY"
        elif self.type == SQLITE:
            return "INTEGER PRIMARY KEY AUTOINCREMENT"
        return "<nothing>"

    @property
    def references_schema(self) -> str:
        if self.type in {POSTGRES, COCKROACH}:
            return f"{self.schema}."
        elif self.type == SQLITE:
            return ""
        return "<nothing>"


class Connection(Compat):
    def __init__(self, conn: AsyncConnection, txn, typ, name, schema):
        self.conn = conn
        self.txn = txn
        self.type = typ
        self.name = name
        self.schema = schema

    def rewrite_query(self, query) -> str:
        if self.type in {POSTGRES, COCKROACH}:
            query = query.replace("%", "%%")
            query = query.replace("?", "%s")
        return query

    async def fetchall(self, query: str, values: tuple = ()) -> list:
        result = await self.conn.execute(self.rewrite_query(query), values)
        return await result.fetchall()

    async def fetchone(self, query: str, values: tuple = ()):
        result = await self.conn.execute(self.rewrite_query(query), values)
        row = await result.fetchone()
        await result.close()
        return row

    async def execute(self, query: str, values: tuple = ()):
        return await self.conn.execute(self.rewrite_query(query), values)


class Database(Compat):
    def __init__(self, db_name: str):
        self.name = db_name

        if LNBITS_DATABASE_URL:
            database_uri = LNBITS_DATABASE_URL

            if database_uri.startswith("cockroachdb://"):
                self.type = COCKROACH
            else:
                self.type = POSTGRES

            import psycopg2  # type: ignore

            psycopg2.extensions.register_type(
                psycopg2.extensions.new_type(
                    psycopg2.extensions.DECIMAL.values,
                    "DEC2FLOAT",
                    lambda value, curs: float(value) if value is not None else None,
                )
            )
            psycopg2.extensions.register_type(
                psycopg2.extensions.new_type(
                    (1082, 1083, 1266),
                    "DATE2INT",
                    lambda value, curs: time.mktime(value.timetuple())
                    if value is not None
                    else None,
                )
            )

            psycopg2.extensions.register_type(
                psycopg2.extensions.new_type(
                    (1184, 1114),
                    "TIMESTAMP2INT",
                    lambda value, curs: time.mktime(
                        datetime.datetime.strptime(
                            value, "%Y-%m-%d %H:%M:%S.%f"
                        ).timetuple()
                    ),
                )
            )
        else:
            self.path = os.path.join(LNBITS_DATA_FOLDER, f"{self.name}.sqlite3")
            database_uri = f"sqlite:///{self.path}"
            self.type = SQLITE

        self.schema = self.name
        if self.name.startswith("ext_"):
            self.schema = self.name[4:]
        else:
            self.schema = None

        self.engine = create_engine(database_uri, strategy=TRIO_STRATEGY)
        self.lock = trio.StrictFIFOLock()

    @asynccontextmanager
    async def connect(self):
        await self.lock.acquire()
        try:
            async with self.engine.connect() as conn:
                async with conn.begin() as txn:
                    wconn = Connection(conn, txn, self.type, self.name, self.schema)

                    if self.schema:
                        if self.type in {POSTGRES, COCKROACH}:
                            await wconn.execute(
                                f"CREATE SCHEMA IF NOT EXISTS {self.schema}"
                            )
                        elif self.type == SQLITE:
                            await wconn.execute(
                                f"ATTACH '{self.path}' AS {self.schema}"
                            )

                    yield wconn
        finally:
            self.lock.release()

    async def fetchall(self, query: str, values: tuple = ()) -> list:
        async with self.connect() as conn:
            result = await conn.execute(query, values)
            return await result.fetchall()

    async def fetchone(self, query: str, values: tuple = ()):
        async with self.connect() as conn:
            result = await conn.execute(query, values)
            row = await result.fetchone()
            await result.close()
            return row

    async def execute(self, query: str, values: tuple = ()):
        async with self.connect() as conn:
            return await conn.execute(query, values)

    @asynccontextmanager
    async def reuse_conn(self, conn: Connection):
        yield conn
