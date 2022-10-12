from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import createLnurldevice, lnurldevicepayment, lnurldevices

###############lnurldeviceS##########################


async def create_lnurldevice(
    data: createLnurldevice,
) -> lnurldevices:
    lnurldevice_id = urlsafe_short_hash()
    lnurldevice_key = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO lnurldevice.lnurldevices (
            id,
            key,
            title,
            wallet,
            currency,
            device,
            profit,
            amount
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lnurldevice_id,
            lnurldevice_key,
            data.title,
            data.wallet,
            data.currency,
            data.device,
            data.profit,
            data.amount,
        ),
    )
    return await get_lnurldevice(lnurldevice_id)


async def update_lnurldevice(lnurldevice_id: str, **kwargs) -> Optional[lnurldevices]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE lnurldevice.lnurldevices SET {q} WHERE id = ?",
        (*kwargs.values(), lnurldevice_id),
    )
    row = await db.fetchone(
        "SELECT * FROM lnurldevice.lnurldevices WHERE id = ?", (lnurldevice_id,)
    )
    return lnurldevices(**row) if row else None


async def get_lnurldevice(lnurldevice_id: str) -> lnurldevices:
    row = await db.fetchone(
        "SELECT * FROM lnurldevice.lnurldevices WHERE id = ?", (lnurldevice_id,)
    )
    return lnurldevices(**row) if row else None


async def get_lnurldevices(wallet_ids: Union[str, List[str]]) -> List[lnurldevices]:
    wallet_ids = [wallet_ids]
    q = ",".join(["?"] * len(wallet_ids[0]))
    rows = await db.fetchall(
        f"""
        SELECT * FROM lnurldevice.lnurldevices WHERE wallet IN ({q})
        ORDER BY id
        """,
        (*wallet_ids,),
    )

    return [lnurldevices(**row) if row else None for row in rows]


async def delete_lnurldevice(lnurldevice_id: str) -> None:
    await db.execute(
        "DELETE FROM lnurldevice.lnurldevices WHERE id = ?", (lnurldevice_id,)
    )

    ########################lnuldevice payments###########################


async def create_lnurldevicepayment(
    deviceid: str,
    payload: Optional[str] = None,
    pin: Optional[str] = None,
    payhash: Optional[str] = None,
    sats: Optional[int] = 0,
) -> lnurldevicepayment:
    lnurldevicepayment_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO lnurldevice.lnurldevicepayment (
            id,
            deviceid,
            payload,
            pin,
            payhash,
            sats
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (lnurldevicepayment_id, deviceid, payload, pin, payhash, sats),
    )
    return await get_lnurldevicepayment(lnurldevicepayment_id)


async def update_lnurldevicepayment(
    lnurldevicepayment_id: str, **kwargs
) -> Optional[lnurldevicepayment]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE lnurldevice.lnurldevicepayment SET {q} WHERE id = ?",
        (*kwargs.values(), lnurldevicepayment_id),
    )
    row = await db.fetchone(
        "SELECT * FROM lnurldevice.lnurldevicepayment WHERE id = ?",
        (lnurldevicepayment_id,),
    )
    return lnurldevicepayment(**row) if row else None


async def get_lnurldevicepayment(lnurldevicepayment_id: str) -> lnurldevicepayment:
    row = await db.fetchone(
        "SELECT * FROM lnurldevice.lnurldevicepayment WHERE id = ?",
        (lnurldevicepayment_id,),
    )
    return lnurldevicepayment(**row) if row else None


async def get_lnurlpayload(lnurldevicepayment_payload: str) -> lnurldevicepayment:
    row = await db.fetchone(
        "SELECT * FROM lnurldevice.lnurldevicepayment WHERE payload = ?",
        (lnurldevicepayment_payload,),
    )
    return lnurldevicepayment(**row) if row else None
