from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateLnurlPayoutData, lnurlpayout


async def create_lnurlpayout(
    wallet_id: str, admin_key: str, data: CreateLnurlPayoutData
) -> lnurlpayout:
    lnurlpayout_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO lnurlpayout.lnurlpayouts (id, title, wallet, admin_key, lnurlpay, threshold)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            lnurlpayout_id,
            data.title,
            wallet_id,
            admin_key,
            data.lnurlpay,
            data.threshold,
        ),
    )

    lnurlpayout = await get_lnurlpayout(lnurlpayout_id)
    assert lnurlpayout, "Newly created lnurlpayout couldn't be retrieved"
    return lnurlpayout


async def get_lnurlpayout(lnurlpayout_id: str) -> Optional[lnurlpayout]:
    row = await db.fetchone(
        "SELECT * FROM lnurlpayout.lnurlpayouts WHERE id = ?", (lnurlpayout_id,)
    )
    return lnurlpayout(**row) if row else None


async def get_lnurlpayout_from_wallet(wallet_id: str) -> Optional[lnurlpayout]:
    row = await db.fetchone(
        "SELECT * FROM lnurlpayout.lnurlpayouts WHERE wallet = ?", (wallet_id,)
    )
    return lnurlpayout(**row) if row else None


async def get_lnurlpayouts(wallet_ids: Union[str, List[str]]) -> List[lnurlpayout]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM lnurlpayout.lnurlpayouts WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [lnurlpayout(**row) if row else None for row in rows]


async def delete_lnurlpayout(lnurlpayout_id: str) -> None:
    await db.execute(
        "DELETE FROM lnurlpayout.lnurlpayouts WHERE id = ?", (lnurlpayout_id,)
    )
