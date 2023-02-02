import asyncio
import datetime
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Optional

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy_aio.base import AsyncConnection
from sqlalchemy_aio.strategy import ASYNCIO_STRATEGY

from lnbits.settings import settings

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

    def datetime_to_timestamp(self, date: datetime.datetime):
        if self.type in {POSTGRES, COCKROACH}:
            return date.strftime("%Y-%m-%d %H:%M:%S")
        elif self.type == SQLITE:
            return time.mktime(date.timetuple())
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

    @property
    def big_int(self) -> str:
        if self.type in {POSTGRES}:
            return "BIGINT"
        return "INT"


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

    def rewrite_values(self, values):
        # strip html
        CLEANR = re.compile("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")

        def cleanhtml(raw_html):
            if isinstance(raw_html, str):
                cleantext = re.sub(CLEANR, "", raw_html)
                return cleantext
            else:
                return raw_html

        # tuple to list and back to tuple
        value_list = [values] if isinstance(values, str) else list(values)
        values = tuple([cleanhtml(l) for l in value_list])
        return values

    async def fetchall(self, query: str, values: tuple = ()) -> list:
        result = await self.conn.execute(
            self.rewrite_query(query), self.rewrite_values(values)
        )
        return await result.fetchall()

    async def fetchone(self, query: str, values: tuple = ()):
        result = await self.conn.execute(
            self.rewrite_query(query), self.rewrite_values(values)
        )
        row = await result.fetchone()
        await result.close()
        return row

    async def execute(self, query: str, values: tuple = ()):
        return await self.conn.execute(
            self.rewrite_query(query), self.rewrite_values(values)
        )


class Database(Compat):
    def __init__(self, db_name: str):
        self.name = db_name

        if settings.lnbits_database_url:
            database_uri = settings.lnbits_database_url

            if database_uri.startswith("cockroachdb://"):
                self.type = COCKROACH
            else:
                self.type = POSTGRES

            from psycopg2.extensions import DECIMAL, new_type, register_type

            def _parse_timestamp(value, _):
                if value is None:
                    return None
                f = "%Y-%m-%d %H:%M:%S.%f"
                if "." not in value:
                    f = "%Y-%m-%d %H:%M:%S"
                return time.mktime(datetime.datetime.strptime(value, f).timetuple())

            register_type(
                new_type(
                    DECIMAL.values,
                    "DEC2FLOAT",
                    lambda value, curs: float(value) if value is not None else None,
                )
            )
            register_type(
                new_type(
                    (1082, 1083, 1266),
                    "DATE2INT",
                    lambda value, curs: time.mktime(value.timetuple())
                    if value is not None
                    else None,
                )
            )

            register_type(new_type((1184, 1114), "TIMESTAMP2INT", _parse_timestamp))
        else:
            if os.path.isdir(settings.lnbits_data_folder):
                self.path = os.path.join(
                    settings.lnbits_data_folder, f"{self.name}.sqlite3"
                )
                database_uri = f"sqlite:///{self.path}"
                self.type = SQLITE
            else:
                raise NotADirectoryError(
                    f"LNBITS_DATA_FOLDER named {settings.lnbits_data_folder} was not created"
                    f" - please 'mkdir {settings.lnbits_data_folder}' and try again"
                )
        logger.trace(f"database {self.type} added for {self.name}")
        self.schema = self.name
        if self.name.startswith("ext_"):
            self.schema = self.name[4:]
        else:
            self.schema = None

        self.engine = create_engine(database_uri, strategy=ASYNCIO_STRATEGY)
        self.lock = asyncio.Lock()

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
