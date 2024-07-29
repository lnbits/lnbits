from __future__ import annotations

import asyncio
import datetime
import os
import re
import time
from contextlib import asynccontextmanager
from enum import Enum
from sqlite3 import Row
from typing import Any, Generic, Literal, Optional, TypeVar

from loguru import logger
from pydantic import BaseModel, ValidationError, root_validator
from sqlalchemy import create_engine
from sqlalchemy_aio.base import AsyncConnection
from sqlalchemy_aio.strategy import ASYNCIO_STRATEGY

from lnbits.settings import settings

POSTGRES = "POSTGRES"
COCKROACH = "COCKROACH"
SQLITE = "SQLITE"

if settings.lnbits_database_url:
    database_uri = settings.lnbits_database_url

    if database_uri.startswith("cockroachdb://"):
        DB_TYPE = COCKROACH
    else:
        DB_TYPE = POSTGRES

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

    register_type(new_type((1184, 1114), "TIMESTAMP2INT", _parse_timestamp))
else:
    if not os.path.isdir(settings.lnbits_data_folder):
        os.mkdir(settings.lnbits_data_folder)
        logger.info(f"Created {settings.lnbits_data_folder}")
    DB_TYPE = SQLITE


def compat_timestamp_placeholder():
    if DB_TYPE == POSTGRES:
        return "to_timestamp(?)"
    elif DB_TYPE == COCKROACH:
        return "cast(? AS timestamp)"
    else:
        return "?"


def get_placeholder(model: Any, field: str) -> str:
    type_ = model.__fields__[field].type_
    if type_ == datetime.datetime:
        return compat_timestamp_placeholder()
    else:
        return "?"


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
    def timestamp_column_default(self) -> str:
        if self.type in {POSTGRES, COCKROACH}:
            return self.timestamp_now
        return "NULL"

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

    @property
    def timestamp_placeholder(self) -> str:
        return compat_timestamp_placeholder()


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
        clean_regex = re.compile("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")

        # tuple to list and back to tuple
        raw_values = [values] if isinstance(values, str) else list(values)
        values = []
        for raw_value in raw_values:
            if isinstance(raw_value, str):
                values.append(re.sub(clean_regex, "", raw_value))
            elif isinstance(raw_value, datetime.datetime):
                ts = raw_value.timestamp()
                if self.type == SQLITE:
                    values.append(int(ts))
                else:
                    values.append(ts)
            else:
                values.append(raw_value)
        return tuple(values)

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

    async def fetch_page(
        self,
        query: str,
        where: Optional[list[str]] = None,
        values: Optional[list[str]] = None,
        filters: Optional[Filters] = None,
        model: Optional[type[TRowModel]] = None,
        group_by: Optional[list[str]] = None,
    ) -> Page[TRowModel]:
        if not filters:
            filters = Filters()
        clause = filters.where(where)
        parsed_values = filters.values(values)

        group_by_string = ""
        if group_by:
            for field in group_by:
                if not re.fullmatch(
                    r"[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?", field
                ):
                    raise ValueError("Value for GROUP BY is invalid")
            group_by_string = f"GROUP BY {', '.join(group_by)}"

        rows = await self.fetchall(
            f"""
            {query}
            {clause}
            {group_by_string}
            {filters.order_by()}
            {filters.pagination()}
            """,
            parsed_values,
        )
        if rows:
            # no need for extra query if no pagination is specified
            if filters.offset or filters.limit:
                count = await self.fetchone(
                    f"""
                    SELECT COUNT(*) FROM (
                        {query}
                        {clause}
                        {group_by_string}
                    ) as count
                    """,
                    parsed_values,
                )
                count = int(count[0])
            else:
                count = len(rows)
        else:
            count = 0

        return Page(
            data=[model.from_row(row) for row in rows] if model else rows,
            total=count,
        )

    async def execute(self, query: str, values: tuple = ()):
        return await self.conn.execute(
            self.rewrite_query(query), self.rewrite_values(values)
        )


class Database(Compat):
    def __init__(self, db_name: str):
        self.name = db_name
        self.schema = self.name
        self.type = DB_TYPE

        if DB_TYPE == SQLITE:
            self.path = os.path.join(
                settings.lnbits_data_folder, f"{self.name}.sqlite3"
            )
            database_uri = f"sqlite:///{self.path}"
        else:
            database_uri = settings.lnbits_database_url

        if self.name.startswith("ext_"):
            self.schema = self.name[4:]
        else:
            self.schema = None

        self.engine = create_engine(
            database_uri, strategy=ASYNCIO_STRATEGY, echo=settings.debug_database
        )
        self.lock = asyncio.Lock()

        logger.trace(f"database {self.type} added for {self.name}")

    @asynccontextmanager
    async def connect(self):
        await self.lock.acquire()
        try:
            async with self.engine.connect() as conn:  # type: ignore
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

    async def fetch_page(
        self,
        query: str,
        where: Optional[list[str]] = None,
        values: Optional[list[str]] = None,
        filters: Optional[Filters] = None,
        model: Optional[type[TRowModel]] = None,
        group_by: Optional[list[str]] = None,
    ) -> Page[TRowModel]:
        async with self.connect() as conn:
            return await conn.fetch_page(query, where, values, filters, model, group_by)

    async def execute(self, query: str, values: tuple = ()):
        async with self.connect() as conn:
            return await conn.execute(query, values)

    @asynccontextmanager
    async def reuse_conn(self, conn: Connection):
        yield conn

    @classmethod
    async def clean_ext_db_files(cls, ext_id: str) -> bool:
        """
        If the extension DB is stored directly on the filesystem (like SQLite) then
        delete the files and return True. Otherwise do nothing and return False.
        """

        if DB_TYPE == SQLITE:
            db_file = os.path.join(settings.lnbits_data_folder, f"ext_{ext_id}.sqlite3")
            if os.path.isfile(db_file):
                os.remove(db_file)
            return True

        return False


class Operator(Enum):
    GT = "gt"
    LT = "lt"
    EQ = "eq"
    NE = "ne"
    GE = "ge"
    LE = "le"
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
        elif self == Operator.GE:
            return ">="
        elif self == Operator.LE:
            return "<="
        else:
            raise ValueError("Unknown SQL Operator")


class FromRowModel(BaseModel):
    @classmethod
    def from_row(cls, row: Row):
        return cls(**dict(row))


class FilterModel(BaseModel):
    __search_fields__: list[str] = []
    __sort_fields__: Optional[list[str]] = None


T = TypeVar("T")
TModel = TypeVar("TModel", bound=BaseModel)
TRowModel = TypeVar("TRowModel", bound=FromRowModel)
TFilterModel = TypeVar("TFilterModel", bound=FilterModel)


class Page(BaseModel, Generic[T]):
    data: list[T]
    total: int


class Filter(BaseModel, Generic[TFilterModel]):
    field: str
    op: Operator = Operator.EQ
    values: list[Any]

    model: Optional[type[TFilterModel]]

    @classmethod
    def parse_query(cls, key: str, raw_values: list[Any], model: type[TFilterModel]):
        # Key format:
        # key[operator]
        # e.g. name[eq]
        if key.endswith("]"):
            split = key[:-1].split("[")
            if len(split) != 2:
                raise ValueError("Invalid key")
            field = split[0]
            op = Operator(split[1])
        else:
            field = key
            op = Operator("eq")

        if field in model.__fields__:
            compare_field = model.__fields__[field]
            values = []
            for raw_value in raw_values:
                validated, errors = compare_field.validate(raw_value, {}, loc="none")
                if errors:
                    raise ValidationError(errors=[errors], model=model)
                values.append(validated)
        else:
            raise ValueError("Unknown filter field")

        return cls(field=field, op=op, values=values, model=model)

    @property
    def statement(self):
        assert self.model, "Model is required for statement generation"
        placeholder = get_placeholder(self.model, self.field)
        if self.op in (Operator.INCLUDE, Operator.EXCLUDE):
            placeholders = ", ".join([placeholder] * len(self.values))
            stmt = [f"{self.field} {self.op.as_sql} ({placeholders})"]
        else:
            stmt = [f"{self.field} {self.op.as_sql} {placeholder}"] * len(self.values)
        return " OR ".join(stmt)


class Filters(BaseModel, Generic[TFilterModel]):
    """
    Generic helper class for filtering and sorting data.
    For usage in an api endpoint, use the `parse_filters` dependency.

    When constructing this class manually always make sure to pass a model so that
    the values can be validated. Otherwise, make sure to validate the inputs manually.
    """

    filters: list[Filter[TFilterModel]] = []
    search: Optional[str] = None

    offset: Optional[int] = None
    limit: Optional[int] = None

    sortby: Optional[str] = None
    direction: Optional[Literal["asc", "desc"]] = None

    model: Optional[type[TFilterModel]] = None

    @root_validator(pre=True)
    def validate_sortby(cls, values):
        sortby = values.get("sortby")
        model = values.get("model")
        if sortby and model:
            model = values["model"]
            # if no sort fields are specified explicitly all fields are allowed
            allowed = model.__sort_fields__ or model.__fields__
            if sortby not in allowed:
                raise ValueError("Invalid sort field")
        return values

    def pagination(self) -> str:
        stmt = ""
        if self.limit:
            stmt += f"LIMIT {self.limit} "
        if self.offset:
            stmt += f"OFFSET {self.offset}"
        return stmt

    def where(self, where_stmts: Optional[list[str]] = None) -> str:
        if not where_stmts:
            where_stmts = []
        if self.filters:
            for page_filter in self.filters:
                where_stmts.append(page_filter.statement)
        if self.search and self.model:
            if DB_TYPE == POSTGRES:
                where_stmts.append(
                    f"lower(concat({', '.join(self.model.__search_fields__)})) LIKE ?"
                )
            elif DB_TYPE == SQLITE:
                where_stmts.append(
                    f"lower({'||'.join(self.model.__search_fields__)}) LIKE ?"
                )
        if where_stmts:
            return "WHERE " + " AND ".join(where_stmts)
        return ""

    def order_by(self) -> str:
        if self.sortby:
            return f"ORDER BY {self.sortby} {self.direction or 'asc'}"
        return ""

    def values(self, values: Optional[list[str]] = None) -> tuple:
        if not values:
            values = []
        if self.filters:
            for page_filter in self.filters:
                values.extend(page_filter.values)
        if self.search and self.model:
            values.append(f"%{self.search}%")
        return tuple(values)
