import asyncio
import datetime
import os
import re
import time
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Generic, List, Optional, Tuple, Type, TypeVar

from loguru import logger
from pydantic import BaseModel, ValidationError
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

            import psycopg2

            def _parse_timestamp(value, _):
                if value is None:
                    return None
                f = "%Y-%m-%d %H:%M:%S.%f"
                if "." not in value:
                    f = "%Y-%m-%d %H:%M:%S"
                return time.mktime(datetime.datetime.strptime(value, f).timetuple())

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
                    (1184, 1114), "TIMESTAMP2INT", _parse_timestamp
                )
            )
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


class Operator(Enum):
    GT = "gt"
    LT = "lt"
    EQ = "eq"
    NE = "ne"
    INCLUDE = "in"
    EXCLUDE = "ex"

    @property
    def as_sql(self):
        if self == Operator.EQ:
            return "="
        elif self == Operator.NE:
            return "!="
        elif self == Operator.INCLUDE:
            return "IN"
        elif self == Operator.EXCLUDE:
            return "NOT IN"
        elif self == Operator.GT:
            return ">"
        elif self == Operator.LT:
            return "<"
        else:
            raise ValueError("Unknown SQL Operator")


TModel = TypeVar("TModel", bound=BaseModel)


class Filter(BaseModel, Generic[TModel]):
    field: str
    nested: Optional[list[str]]
    op: Operator = Operator.EQ
    values: list[Any]

    @classmethod
    def parse_query(cls, key: str, raw_values: list[Any], model: Type[TModel]):
        # Key format:
        # key[operator]
        # e.g. name[eq]
        if key.endswith("]"):
            split = key[:-1].split("[")
            if len(split) != 2:
                raise ValueError("Invalid key")
            field_names = split[0].split(".")
            op = Operator(split[1])
        else:
            field_names = key.split(".")
            op = Operator("eq")

        field = field_names[0]
        nested = field_names[1:]

        if field in model.__fields__:
            compare_field = model.__fields__[field]
            values = []
            for raw_value in raw_values:
                # If there is a nested field, pydantic expects a dict, so the raw value is turned into a dict before
                # and the converted value is extracted afterwards
                for name in reversed(nested):
                    raw_value = {name: raw_value}

                validated, errors = compare_field.validate(raw_value, {}, loc="none")
                if errors:
                    raise ValidationError(errors=[errors], model=model)

                for name in nested:
                    if isinstance(validated, dict):
                        validated = validated[name]
                    else:
                        validated = getattr(validated, name)

                values.append(validated)
        else:
            raise ValueError("Unknown filter field")

        return cls(field=field, op=op, nested=nested, values=values)

    @property
    def statement(self):
        accessor = self.field
        if self.nested:
            for name in self.nested:
                accessor = f"({accessor} ->> '{name}')"
        if self.op in (Operator.INCLUDE, Operator.EXCLUDE):
            placeholders = ", ".join(["?"] * len(self.values))
            stmt = [f"{accessor} {self.op.as_sql} ({placeholders})"]
        else:
            stmt = [f"{accessor} {self.op.as_sql} ?"] * len(self.values)
        return " OR ".join(stmt)


class Filters(BaseModel, Generic[TModel]):
    filters: List[Filter[TModel]] = []
    limit: Optional[int]
    offset: Optional[int]

    def pagination(self) -> str:
        stmt = ""
        if self.limit:
            stmt += f"LIMIT {self.limit} "
        if self.offset:
            stmt += f"OFFSET {self.offset}"
        return stmt

    def where(self, where_stmts: List[str]) -> str:
        if self.filters:
            for filter in self.filters:
                where_stmts.append(filter.statement)
        if where_stmts:
            return "WHERE " + " AND ".join(where_stmts)
        return ""

    def values(self, values: List[str]) -> Tuple:
        if self.filters:
            for filter in self.filters:
                values.extend(filter.values)
        return tuple(values)
