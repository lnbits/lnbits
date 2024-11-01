from typing import Optional

from lnbits.core.db import db
from lnbits.core.models.extensions import (
    InstallableExtension,
    UserExtension,
)
from lnbits.db import Connection, Database


async def create_installed_extension(
    ext: InstallableExtension,
    conn: Optional[Connection] = None,
) -> None:
    await (conn or db).insert("installed_extensions", ext)


async def update_installed_extension(
    ext: InstallableExtension,
    conn: Optional[Connection] = None,
) -> None:
    await (conn or db).update("installed_extensions", ext)


async def update_installed_extension_state(
    *, ext_id: str, active: bool, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        """
        UPDATE installed_extensions SET active = :active WHERE id = :ext
        """,
        {"ext": ext_id, "active": active},
    )


async def delete_installed_extension(
    *, ext_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        """
        DELETE from installed_extensions  WHERE id = :ext
        """,
        {"ext": ext_id},
    )


async def drop_extension_db(ext_id: str, conn: Optional[Connection] = None) -> None:
    row: dict = await (conn or db).fetchone(
        "SELECT * FROM dbversions WHERE db = :id",
        {"id": ext_id},
    )
    # Check that 'ext_id' is a valid extension id and not a malicious string
    assert row, f"Extension '{ext_id}' db version cannot be found"

    is_file_based_db = await Database.clean_ext_db_files(ext_id)
    if is_file_based_db:
        return

    # String formatting is required, params are not accepted for 'DROP SCHEMA'.
    # The `ext_id` value is verified above.
    await (conn or db).execute(
        f"DROP SCHEMA IF EXISTS {ext_id} CASCADE",
    )


async def get_installed_extension(
    ext_id: str, conn: Optional[Connection] = None
) -> Optional[InstallableExtension]:
    extension = await (conn or db).fetchone(
        "SELECT * FROM installed_extensions WHERE id = :id",
        {"id": ext_id},
        InstallableExtension,
    )
    return extension


async def get_installed_extensions(
    active: Optional[bool] = None,
    conn: Optional[Connection] = None,
) -> list[InstallableExtension]:
    where = "WHERE active = :active" if active is not None else ""
    values = {"active": active} if active is not None else {}
    all_extensions = await (conn or db).fetchall(
        f"SELECT * FROM installed_extensions {where}",
        values,
        model=InstallableExtension,
    )
    return all_extensions


async def get_user_extension(
    user_id: str, extension: str, conn: Optional[Connection] = None
) -> Optional[UserExtension]:
    return await (conn or db).fetchone(
        """
        SELECT * FROM extensions
        WHERE "user" = :user AND extension = :ext
        """,
        {"user": user_id, "ext": extension},
        model=UserExtension,
    )


async def get_user_extensions(
    user_id: str, conn: Optional[Connection] = None
) -> list[UserExtension]:
    return await (conn or db).fetchall(
        """SELECT * FROM extensions WHERE "user" = :user""",
        {"user": user_id},
        model=UserExtension,
    )


async def create_user_extension(
    user_extension: UserExtension, conn: Optional[Connection] = None
) -> None:
    await (conn or db).insert("extensions", user_extension)


async def update_user_extension(
    user_extension: UserExtension, conn: Optional[Connection] = None
) -> None:
    where = """WHERE extension = :extension AND "user" = :user"""
    await (conn or db).update("extensions", user_extension, where)


async def get_user_active_extensions_ids(
    user_id: str, conn: Optional[Connection] = None
) -> list[str]:
    exts = await (conn or db).fetchall(
        """
        SELECT * FROM extensions WHERE "user" = :user AND active
        """,
        {"user": user_id},
        UserExtension,
    )
    return [ext.extension for ext in exts]
