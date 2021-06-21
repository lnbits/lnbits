import os
import trio
from contextlib import asynccontextmanager
from sqlalchemy import create_engine  # type: ignore
from sqlalchemy_aio import TRIO_STRATEGY  # type: ignore
from sqlalchemy_aio.base import AsyncConnection  # type: ignore

from .settings import LNBITS_DATA_FOLDER


class Connection:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def fetchall(self, query: str, values: tuple = ()) -> list:
        result = await self.conn.execute(query, values)
        return await result.fetchall()

    async def fetchone(self, query: str, values: tuple = ()):
        result = await self.conn.execute(query, values)
        row = await result.fetchone()
        await result.close()
        return row

    async def execute(self, query: str, values: tuple = ()):
        return await self.conn.execute(query, values)


class Database:
    def __init__(self, db_name: str):
        self.db_name = db_name
        db_path = os.path.join(LNBITS_DATA_FOLDER, f"{db_name}.sqlite3")
        self.engine = create_engine(f"sqlite:///{db_path}", strategy=TRIO_STRATEGY)
        self.lock = trio.StrictFIFOLock()

    @asynccontextmanager
    async def connect(self):
        await self.lock.acquire()
        try:
            async with self.engine.connect() as conn:
                async with conn.begin():
                    yield Connection(conn)
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
