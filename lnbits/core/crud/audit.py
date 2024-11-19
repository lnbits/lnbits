from typing import Optional

from lnbits.core.db import db
from lnbits.core.models import AuditEntry
from lnbits.db import Connection


async def create_audit_entry(
    entry: AuditEntry,
    conn: Optional[Connection] = None,
) -> None:
    await (conn or db).insert("audit", entry)
