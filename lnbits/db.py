import os
from typing import Tuple, Optional, Any
from sqlalchemy_aio import TRIO_STRATEGY  # type: ignore
from sqlalchemy import create_engine  # type: ignore
from quart import g

from .settings import LNBITS_DATA_FOLDER


class Database:
    def __init__(self, db_name: str):
        self.db_name = db_name
        db_path = os.path.join(LNBITS_DATA_FOLDER, f"{db_name}.sqlite3")
        self.engine = create_engine(f"sqlite:///{db_path}", strategy=TRIO_STRATEGY)

    def connect(self):
        return self.engine.connect()

    def session_connection(self) -> Tuple[Optional[Any], Optional[Any]]:
        try:
            return getattr(g, f"{self.db_name}_conn", None), getattr(
                g, f"{self.db_name}_txn", None
            )
        except RuntimeError:
            return None, None

    async def begin(self):
        conn, _ = self.session_connection()
        if conn:
            return

        conn = await self.engine.connect()
        setattr(g, f"{self.db_name}_conn", conn)
        txn = await conn.begin()
        setattr(g, f"{self.db_name}_txn", txn)

    async def fetchall(self, query: str, values: tuple = ()) -> list:
        conn, _ = self.session_connection()
        if conn:
            result = await conn.execute(query, values)
            return await result.fetchall()

        async with self.connect() as conn:
            result = await conn.execute(query, values)
            return await result.fetchall()

    async def fetchone(self, query: str, values: tuple = ()):
        conn, _ = self.session_connection()
        if conn:
            result = await conn.execute(query, values)
            row = await result.fetchone()
            await result.close()
            return row

        async with self.connect() as conn:
            result = await conn.execute(query, values)
            row = await result.fetchone()
            await result.close()
            return row

    async def execute(self, query: str, values: tuple = ()):
        conn, _ = self.session_connection()
        if conn:
            return await conn.execute(query, values)

        async with self.connect() as conn:
            return await conn.execute(query, values)

    async def commit(self):
        conn, txn = self.session_connection()
        if conn and txn:
            await txn.commit()
            await self.close_session()

    async def rollback(self):
        conn, txn = self.session_connection()
        if conn and txn:
            await txn.rollback()
            await self.close_session()

    async def close_session(self):
        conn, txn = self.session_connection()
        if conn and txn:
            await txn.close()
            await conn.close()
            delattr(g, f"{self.db_name}_conn")
            delattr(g, f"{self.db_name}_txn")
