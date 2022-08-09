from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateTposData, TPoS


async def create_tpos(wallet_id: str, data: CreateTposData) -> TPoS:
    tpos_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO tpos.tposs (id, wallet, name, currency, tip_options, tip_wallet)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            tpos_id,
            wallet_id,
            data.name,
            data.currency,
            data.tip_options,
            data.tip_wallet,
        ),
    )

    tpos = await get_tpos(tpos_id)
    assert tpos, "Newly created tpos couldn't be retrieved"
    return tpos


async def get_tpos(tpos_id: str) -> Optional[TPoS]:
    row = await db.fetchone("SELECT * FROM tpos.tposs WHERE id = ?", (tpos_id,))
    return TPoS(**row) if row else None


async def get_tposs(wallet_ids: Union[str, List[str]]) -> List[TPoS]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM tpos.tposs WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [TPoS(**row) for row in rows]


async def delete_tpos(tpos_id: str) -> None:
    await db.execute("DELETE FROM tpos.tposs WHERE id = ?", (tpos_id,))

def bech32_decode(bech):
    """tweaked version of bech32_decode that ignores length limitations"""
    if (any(ord(x) < 33 or ord(x) > 126 for x in bech)) or (
        bech.lower() != bech and bech.upper() != bech
    ):
        return
    bech = bech.lower()
    device = bech.rfind("1")
    if device < 1 or device + 7 > len(bech):
        return
    if not all(x in bech32.CHARSET for x in bech[device + 1 :]):
        return
    hrp = bech[:device]
    data = [bech32.CHARSET.find(x) for x in bech[device + 1 :]]
    encoding = bech32.bech32_verify_checksum(hrp, data)
    if encoding is None:
        return
    return bytes(bech32.convertbits(data[:-6], 5, 8, False))
