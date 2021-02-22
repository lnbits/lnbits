from typing import List, Optional, Union

#from lnbits.db import open_ext_db
from . import db
from .models import Charges

from lnbits.helpers import urlsafe_short_hash

from quart import jsonify
import httpx


###############CHARGES##########################


async def create_charge(walletid: str, user: str, title: Optional[str] = None, time: Optional[int] = None, amount: Optional[int] = None) -> Charges:
    wallet = await get_watch_wallet(walletid)
    address = await get_derive_address(walletid, wallet[4] + 1)

    charge_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO charges (
            id,
            user,
            title,
            wallet,
            address,
            time_to_pay,
            amount,
            balance
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (charge_id, user, title,  walletid, address, time, amount, 0),
    )
    return await get_charge(charge_id)


async def get_charge(charge_id: str) -> Charges:
    row = await db.fetchone("SELECT * FROM charges WHERE id = ?", (charge_id,))
    return Charges.from_row(row) if row else None


async def get_charges(user: str) -> List[Charges]:
    rows = await db.fetchall("SELECT * FROM charges WHERE user = ?", (user,))
    for row in rows:
        await check_address_balance(row.address)
    rows = await db.fetchall("SELECT * FROM charges WHERE user = ?", (user,))
    return [charges.from_row(row) for row in rows]


async def delete_charge(charge_id: str) -> None:
    await db.execute("DELETE FROM charges WHERE id = ?", (charge_id,))

async def check_address_balance(address: str) -> List[Charges]:
    address_data = await get_address(address)
    mempool = await get_mempool(address_data.user)

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(mempool.endpoint + "/api/address/" + address)
    except Exception:
        pass

    amount_paid = r.json()['chain_stats']['funded_txo_sum'] - r.json()['chain_stats']['spent_txo_sum']
    print(amount_paid)
