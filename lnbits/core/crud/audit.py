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


async def get_audit_stats(
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
            ORDER BY total DESC
        """,
        values=filters.values(),
        model=AuditCountStat,
    )

    return request_methods
