import json

from lnbits.core.db import db
from lnbits.core.models.two_factor import TwoFactorConfig
from lnbits.db import Connection


async def get_two_factor_config(
    user_id: str, conn: Connection | None = None
) -> tuple[TwoFactorConfig, str | None]:
    row: dict | None = await (conn or db).fetchone(
        "SELECT two_factor FROM accounts WHERE id = :id", {"id": user_id}
    )
    if not row:
        raise ValueError("Account not found.")
    raw = row["two_factor"]
    return (TwoFactorConfig.parse_raw(raw) if raw else TwoFactorConfig(), raw)


async def save_two_factor_config(
    user_id: str, config: TwoFactorConfig, previous: str | None
) -> bool:
    """Compare-and-swap makes consumption atomic across processes and databases."""
    result = await db.execute(
        """UPDATE accounts SET two_factor = :value WHERE id = :id
        AND (two_factor = :previous OR (two_factor IS NULL AND :previous IS NULL))""",
        {"id": user_id, "value": config.json(), "previous": previous},
    )
    return result.rowcount == 1


async def get_two_factor_policy_revision(conn: Connection | None = None) -> str:
    row: dict | None = await (conn or db).fetchone(
        "SELECT value FROM system_settings WHERE id = 'two_factor_revision' "
        "AND tag = 'security'"
    )
    return json.loads(row["value"]) if row else ""
