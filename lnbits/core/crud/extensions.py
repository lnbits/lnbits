import json
from datetime import datetime, timedelta, timezone

from lnbits.core.db import db
from lnbits.core.models.extensions import (
    InstallableExtension,
    UserExtension,
    WasmInvocation,
    WasmInvocationStats,
)
from lnbits.db import Connection, Database


async def create_installed_extension(
    ext: InstallableExtension,
    conn: Connection | None = None,
) -> None:
    await (conn or db).insert("installed_extensions", ext)
    await update_installed_extension_wasm_runtime_limits(
        ext_id=ext.id,
        limits=ext.wasm_runtime_limits,
        conn=conn,
    )


async def update_installed_extension(
    ext: InstallableExtension,
    conn: Connection | None = None,
) -> None:
    await (conn or db).update("installed_extensions", ext)
    await update_installed_extension_wasm_runtime_limits(
        ext_id=ext.id,
        limits=ext.wasm_runtime_limits,
        conn=conn,
    )


async def update_installed_extension_state(
    *, ext_id: str, active: bool, conn: Connection | None = None
) -> None:
    await (conn or db).execute(
        """
        UPDATE installed_extensions SET active = :active WHERE id = :ext
        """,
        {"ext": ext_id, "active": active},
    )


async def update_installed_extension_wasm_runtime_limits(
    *, ext_id: str, limits: dict, conn: Connection | None = None
) -> None:
    if not await _has_installed_extension_wasm_runtime_limits_column(conn=conn):
        return

    await (conn or db).execute(
        """
        UPDATE installed_extensions
        SET wasm_runtime_limits = :limits
        WHERE id = :id
        """,
        {"id": ext_id, "limits": json.dumps(limits)},
    )


async def _has_installed_extension_wasm_runtime_limits_column(
    conn: Connection | None = None,
) -> bool:
    row: dict | None = await (conn or db).fetchone(
        "SELECT version FROM dbversions WHERE db = 'core'"
    )
    if not row:
        return False
    return int(row["version"] or 0) >= 48


async def delete_installed_extension(
    *, ext_id: str, conn: Connection | None = None
) -> None:
    await (conn or db).execute(
        """
        DELETE from installed_extensions  WHERE id = :ext
        """,
        {"ext": ext_id},
    )


async def drop_extension_db(ext_id: str, conn: Connection | None = None) -> None:
    row: dict = await (conn or db).fetchone(
        "SELECT * FROM dbversions WHERE db = :id",
        {"id": ext_id},
    )
    # Check that 'ext_id' is a valid extension id and not a malicious string
    if not row:
        raise Exception(f"Extension '{ext_id}' db version cannot be found")

    is_file_based_db = await Database.clean_ext_db_files(ext_id)
    if is_file_based_db:
        return

    # String formatting is required, params are not accepted for 'DROP SCHEMA'.
    # The `ext_id` value is verified above.
    await (conn or db).execute(
        f"DROP SCHEMA IF EXISTS {ext_id} CASCADE",
    )


async def get_installed_extension(
    ext_id: str, conn: Connection | None = None
) -> InstallableExtension | None:
    extension = await (conn or db).fetchone(
        "SELECT * FROM installed_extensions WHERE id = :id",
        {"id": ext_id},
        InstallableExtension,
    )
    return extension


async def get_installed_extensions(
    active: bool | None = None,
    conn: Connection | None = None,
) -> list[InstallableExtension]:
    query = "SELECT * FROM installed_extensions"
    if active is not None:
        query += " WHERE active = :active"

    values = {"active": active} if active is not None else {}
    all_extensions = await (conn or db).fetchall(
        query,
        values,
        model=InstallableExtension,
    )
    return all_extensions


async def get_installed_extensions_count(conn: Connection | None = None) -> int:
    row: dict | None = await (conn or db).fetchone(
        "SELECT COUNT(*) as count FROM installed_extensions"
    )
    return int(row["count"]) if row else 0


async def get_user_extension(
    user_id: str, extension: str, conn: Connection | None = None
) -> UserExtension | None:
    return await (conn or db).fetchone(
        """
        SELECT * FROM extensions
        WHERE "user" = :user AND extension = :ext
        """,
        {"user": user_id, "ext": extension},
        model=UserExtension,
    )


async def get_user_extensions(
    user_id: str, conn: Connection | None = None
) -> list[UserExtension]:
    return await (conn or db).fetchall(
        """SELECT * FROM extensions WHERE "user" = :user""",
        {"user": user_id},
        model=UserExtension,
    )


async def create_user_extension(
    user_extension: UserExtension, conn: Connection | None = None
) -> None:
    await (conn or db).insert("extensions", user_extension)


async def update_user_extension(
    user_extension: UserExtension, conn: Connection | None = None
) -> None:
    where = """WHERE extension = :extension AND "user" = :user"""
    await (conn or db).update("extensions", user_extension, where)


async def get_user_active_extensions_ids(
    user_id: str, conn: Connection | None = None
) -> list[str]:
    exts = await (conn or db).fetchall(
        """
        SELECT * FROM extensions WHERE "user" = :user AND active
        """,
        {"user": user_id},
        UserExtension,
    )
    return [ext.extension for ext in exts]


async def create_wasm_invocation(
    invocation: WasmInvocation,
    conn: Connection | None = None,
) -> None:
    await (conn or db).insert("wasm_invocations", invocation)


async def update_wasm_invocation(
    invocation: WasmInvocation,
    conn: Connection | None = None,
) -> None:
    await (conn or db).update("wasm_invocations", invocation)


async def get_wasm_invocation(
    invocation_id: str,
    conn: Connection | None = None,
) -> WasmInvocation | None:
    return await (conn or db).fetchone(
        "SELECT * FROM wasm_invocations WHERE id = :id",
        {"id": invocation_id},
        model=WasmInvocation,
    )


async def get_wasm_invocations(
    *,
    extension_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    conn: Connection | None = None,
) -> list[WasmInvocation]:
    where: list[str] = []
    values: dict = {
        "limit": max(1, min(limit, 500)),
        "offset": max(offset, 0),
    }
    if extension_id:
        where.append("extension_id = :extension_id")
        values["extension_id"] = extension_id
    if status:
        where.append("status = :status")
        values["status"] = status

    query = "SELECT * FROM wasm_invocations"
    if where:
        query += f" WHERE {' AND '.join(where)}"
    query += " ORDER BY started_at DESC LIMIT :limit OFFSET :offset"

    return await (conn or db).fetchall(query, values, model=WasmInvocation)


async def get_running_wasm_invocations(
    conn: Connection | None = None,
) -> list[WasmInvocation]:
    return await get_wasm_invocations(status="running", conn=conn)


async def get_wasm_invocation_stats(
    *,
    extension_id: str | None = None,
    since: datetime | None = None,
    conn: Connection | None = None,
) -> WasmInvocationStats:
    where: list[str] = []
    values: dict = {}
    if extension_id:
        where.append("extension_id = :extension_id")
        values["extension_id"] = extension_id
    if since:
        where.append("started_at >= :since")
        values["since"] = since

    query = """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END), 0)
                AS running,
            COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0)
                AS completed,
            COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0)
                AS failed,
            COALESCE(SUM(CASE WHEN status = 'stopped' THEN 1 ELSE 0 END), 0)
                AS stopped,
            COALESCE(SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END), 0)
                AS timeout,
            COALESCE(AVG(duration_ms), 0) AS avg_duration_ms,
            COALESCE(MAX(duration_ms), 0) AS max_duration_ms,
            COALESCE(SUM(host_call_count), 0) AS host_call_count,
            COALESCE(SUM(http_call_count), 0) AS http_call_count,
            COALESCE(SUM(storage_call_count), 0) AS storage_call_count,
            COALESCE(SUM(wallet_call_count), 0) AS wallet_call_count
        FROM wasm_invocations
    """
    if where:
        query += f" WHERE {' AND '.join(where)}"

    row: dict | None = await (conn or db).fetchone(query, values)
    if not row:
        return WasmInvocationStats()

    return WasmInvocationStats(
        total=int(row["total"] or 0),
        running=int(row["running"] or 0),
        completed=int(row["completed"] or 0),
        failed=int(row["failed"] or 0),
        stopped=int(row["stopped"] or 0),
        timeout=int(row["timeout"] or 0),
        avg_duration_ms=float(row["avg_duration_ms"] or 0),
        max_duration_ms=int(row["max_duration_ms"] or 0),
        host_call_count=int(row["host_call_count"] or 0),
        http_call_count=int(row["http_call_count"] or 0),
        storage_call_count=int(row["storage_call_count"] or 0),
        wallet_call_count=int(row["wallet_call_count"] or 0),
    )


async def delete_old_wasm_invocations(
    retention_days: int,
    conn: Connection | None = None,
) -> int:
    if retention_days <= 0:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await (conn or db).execute(
        """
        DELETE FROM wasm_invocations
        WHERE status != 'running' AND started_at < :cutoff
        """,
        {"cutoff": cutoff},
    )
    return int(result.rowcount or 0)


async def mark_stale_wasm_invocations(
    conn: Connection | None = None,
) -> None:
    await (conn or db).execute(
        """
        UPDATE wasm_invocations
        SET status = 'abandoned',
            finished_at = :finished_at,
            stop_reason = 'Server restarted before invocation finished.'
        WHERE status = 'running'
        """,
        {"finished_at": datetime.now(timezone.utc)},
    )
