from typing import Optional

from lnbits.core.db import db
from lnbits.db import Connection

from ..models import DbVersion


async def get_db_version(
    ext_id: str, conn: Optional[Connection] = None
) -> Optional[DbVersion]:
    return await (conn or db).fetchone(
        "SELECT * FROM dbversions WHERE db = :ext_id",
        {"ext_id": ext_id},
        model=DbVersion,
    )


async def get_db_versions(conn: Optional[Connection] = None) -> list[DbVersion]:
    return await (conn or db).fetchall("SELECT * FROM dbversions", model=DbVersion)


async def update_migration_version(conn, db_name, version):
    await (conn or db).execute(
        """
        INSERT INTO dbversions (db, version) VALUES (:db, :version)
        ON CONFLICT (db) DO UPDATE SET version = :version
        """,
        {"db": db_name, "version": version},
    )


async def delete_dbversion(*, ext_id: str, conn: Optional[Connection] = None) -> None:
    await (conn or db).execute(
        """
        DELETE FROM dbversions WHERE db = :ext
        """,
        {"ext": ext_id},
    )
