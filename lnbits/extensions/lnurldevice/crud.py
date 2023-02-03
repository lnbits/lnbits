from typing import List, Optional

import shortuuid

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import createLnurldevice, lnurldevicepayment, lnurldevices


async def create_lnurldevice(
    data: createLnurldevice,
) -> lnurldevices:
    if data.device == "pos" or data.device == "atm":
        lnurldevice_id = shortuuid.uuid()[:5]
    else:
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
            amount,
            pin,
            profit1,
            amount1,
            pin1,
            profit2,
            amount2,
            pin2,
            profit3,
            amount3,
            pin3,
            profit4,
            amount4,
            pin4
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.pin,
            data.profit1,
            data.amount1,
            data.pin1,
            data.profit2,
            data.amount2,
            data.pin2,
            data.profit3,
            data.amount3,
            data.pin3,
            data.profit4,
            data.amount4,
            data.pin4,
        ),
    )
    device = await get_lnurldevice(lnurldevice_id)
    assert device
    return device


async def update_lnurldevice(lnurldevice_id: str, **kwargs) -> lnurldevices:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE lnurldevice.lnurldevices SET {q} WHERE id = ?",
        (*kwargs.values(), lnurldevice_id),
    )
    row = await db.fetchone(
        "SELECT * FROM lnurldevice.lnurldevices WHERE id = ?", (lnurldevice_id,)
    )
    return lnurldevices(**row)


async def get_lnurldevice(lnurldevice_id: str) -> Optional[lnurldevices]:
    row = await db.fetchone(
        "SELECT * FROM lnurldevice.lnurldevices WHERE id = ?", (lnurldevice_id,)
    )
    return lnurldevices(**row) if row else None


async def get_lnurldevices(wallet_ids: List[str]) -> List[lnurldevices]:
    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT * FROM lnurldevice.lnurldevices WHERE wallet IN ({q})
        ORDER BY id
        """,
        (*wallet_ids,),
    )

    return [lnurldevices(**row) for row in rows]


async def delete_lnurldevice(lnurldevice_id: str) -> None:
    await db.execute(
        "DELETE FROM lnurldevice.lnurldevices WHERE id = ?", (lnurldevice_id,)
    )


async def create_lnurldevicepayment(
    deviceid: str,
    payload: Optional[str] = None,
    pin: Optional[str] = None,
    payhash: Optional[str] = None,
    sats: Optional[int] = 0,
) -> lnurldevicepayment:
    device = await get_lnurldevice(deviceid)
    assert device
    if device.device == "atm":
        lnurldevicepayment_id = shortuuid.uuid(name=payload)
    else:
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
    dpayment = await get_lnurldevicepayment(lnurldevicepayment_id)
    assert dpayment
    return dpayment


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


async def get_lnurldevicepayment(
    lnurldevicepayment_id: str,
) -> Optional[lnurldevicepayment]:
    row = await db.fetchone(
        "SELECT * FROM lnurldevice.lnurldevicepayment WHERE id = ?",
        (lnurldevicepayment_id,),
    )
    return lnurldevicepayment(**row) if row else None


async def get_lnurlpayload(
    lnurldevicepayment_payload: str,
) -> Optional[lnurldevicepayment]:
    row = await db.fetchone(
        "SELECT * FROM lnurldevice.lnurldevicepayment WHERE payload = ?",
        (lnurldevicepayment_payload,),
    )
    return lnurldevicepayment(**row) if row else None
