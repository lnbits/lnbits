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
    q = f"""
            DELETE from audit
            WHERE delete_at < {db.timestamp_now}
        """
    print("### q", q)
    await (conn or db).execute(
        f"""
            DELETE from audit
            WHERE delete_at < {db.timestamp_now}
        """,
    )


async def get_request_method_stats(
    filters: Optional[Filters[AuditFilters]] = None,
    conn: Optional[Connection] = None,
) -> list[AuditCountStat]:
    if not filters:
        filters = Filters()
    clause = filters.where()
    request_methods = await (conn or db).fetchall(
        query=f"""
            SELECT request_method as field, count(request_method) as total
            FROM audit
            {clause}
            GROUP BY request_method
            ORDER BY request_method
        """,
        values=filters.values(),
        model=AuditCountStat,
    )

    return request_methods


async def get_component_stats(
    filters: Optional[Filters[AuditFilters]] = None,
    conn: Optional[Connection] = None,
) -> list[AuditCountStat]:
    if not filters:
        filters = Filters()
    clause = filters.where()
    components = await (conn or db).fetchall(
        query=f"""
            SELECT component as field, count(component) as total
            FROM audit
            {clause}
            GROUP BY component
            ORDER BY component
        """,
        values=filters.values(),
        model=AuditCountStat,
    )

    return components


async def get_response_codes_stats(
    filters: Optional[Filters[AuditFilters]] = None,
    conn: Optional[Connection] = None,
) -> list[AuditCountStat]:
    if not filters:
        filters = Filters()
    clause = filters.where()
    request_methods = await (conn or db).fetchall(
        query=f"""
            SELECT response_code as field, count(response_code) as total
            FROM audit
            {clause}
            GROUP BY response_code
            ORDER BY response_code
        """,
        values=filters.values(),
        model=AuditCountStat,
    )

    return request_methods


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
