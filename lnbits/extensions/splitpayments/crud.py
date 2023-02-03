from typing import List

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Target


async def get_targets(source_wallet: str) -> List[Target]:
    rows = await db.fetchall(
        "SELECT * FROM splitpayments.targets WHERE source = ?", (source_wallet,)
    )
    return [Target(**row) for row in rows]


async def set_targets(source_wallet: str, targets: List[Target]):
    async with db.connect() as conn:
        await conn.execute(
            "DELETE FROM splitpayments.targets WHERE source = ?", (source_wallet,)
        )
        for target in targets:
            await conn.execute(
                """
                INSERT INTO splitpayments.targets
                  (id, source, wallet, percent, tag, alias)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    urlsafe_short_hash(),
                    source_wallet,
                    target.wallet,
                    target.percent,
                    target.tag,
                    target.alias,
                ),
            )
