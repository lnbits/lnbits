from typing import Optional

from lnbits.core.db import db
from lnbits.core.models import AuditEntry, AuditFilters
from lnbits.core.models.audit import AuditCountStat
from lnbits.db import Connection, Filters, Page


async def create_audit_entry(
    entry: AuditEntry,
    conn: Optional[Connection] = None,
) -> None:
    await (conn or db).insert("audit", entry)


async def get_audit_entries(
    filters: Optional[Filters[AuditFilters]] = None,
    conn: Optional[Connection] = None,
) -> Page[AuditEntry]:
    return await (conn or db).fetch_page(
        "SELECT * from audit",
        [],
        {},
        filters=filters,
        model=AuditEntry,
    )


async def delete_expired_audit_entries(
    conn: Optional[Connection] = None,
):
    await (conn or db).execute(
        f"""
            DELETE from audit
            WHERE delete_at < {db.timestamp_now}
        """,
    )


async def get_count_stats(
    field: str,
    filters: Optional[Filters[AuditFilters]] = None,
    conn: Optional[Connection] = None,
) -> list[AuditCountStat]:
    if field not in ["request_method", "component", "response_code"]:
        return []
    if not filters:
        filters = Filters()
    clause = filters.where()
    data = await (conn or db).fetchall(
        query=f"""
            SELECT {field} as field, count({field}) as total
            FROM audit
            {clause}
            GROUP BY {field}
            ORDER BY {field}
        """,
        values=filters.values(),
        model=AuditCountStat,
    )

    return data


async def get_long_duration_stats(
    filters: Optional[Filters[AuditFilters]] = None,
    conn: Optional[Connection] = None,
) -> list[AuditCountStat]:
    if not filters:
        filters = Filters()
    clause = filters.where()
    long_duration_paths = await (conn or db).fetchall(
        query=f"""
            SELECT path as field, max(duration) as total FROM audit
            {clause}
            GROUP BY path
            ORDER BY total DESC
            LIMIT 5
        """,
        values=filters.values(),
        model=AuditCountStat,
    )

    return long_duration_paths
