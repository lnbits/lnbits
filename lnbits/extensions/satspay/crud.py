from typing import List, Optional, Union

#from lnbits.db import open_ext_db
from . import db
from .models import Charges

from lnbits.helpers import urlsafe_short_hash

from quart import jsonify
import httpx
from lnbits.core.services import create_invoice, check_invoice_status
from ..watchonly.crud import get_watch_wallet, get_derive_address

###############CHARGES##########################


async def create_charge(user: str, description: Optional[str] = None, onchainwallet: Optional[str] = None, lnbitswallet: Optional[str] = None, webhook: Optional[str] = None, time: Optional[int] = None, amount: Optional[int] = None) -> Charges:
    charge_id = urlsafe_short_hash()
    if onchainwallet:
        wallet = await get_watch_wallet(onchainwallet)
        onchainaddress = await get_derive_address(onchainwallet, wallet[4] + 1)
    else:
        onchainaddress = None
    if lnbitswallet:
        payment_hash, payment_request = await create_invoice(
        wallet_id=lnbitswallet,
        amount=amount,
        memo=charge_id)
    else:
        payment_hash = None
        payment_request = None
    await db.execute(
        """
        INSERT INTO charges (
            id,
            user,
            description,
            onchainwallet,
            onchainaddress,
            lnbitswallet,
            payment_request,
            payment_hash,
            webhook,
            time,
            amount,
            balance,
            paid
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (charge_id, user, description, onchainwallet, onchainaddress, lnbitswallet, payment_request, payment_hash, webhook, time, amount, 0, False),
    )
    return await get_charge(charge_id)

async def update_charge(charge_id: str, **kwargs) -> Optional[Charges]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(f"UPDATE charges SET {q} WHERE id = ?", (*kwargs.values(), wallet_id))
    row = await db.fetchone("SELECT * FROM charges WHERE id = ?", (wallet_id,))
    return Charges.from_row(row) if row else None


async def get_charge(charge_id: str) -> Charges:
    row = await db.fetchone("SELECT * FROM charges WHERE id = ?", (charge_id,))
    return Charges.from_row(row) if row else None


async def get_charges(user: str) -> List[Charges]:
    rows = await db.fetchall("SELECT * FROM charges WHERE user = ?", (user,))
    for row in rows:
        await check_address_balance(row.id)
    rows = await db.fetchall("SELECT * FROM charges WHERE user = ?", (user,))
    return [charges.from_row(row) for row in rows]


async def delete_charge(charge_id: str) -> None:
    await db.execute("DELETE FROM charges WHERE id = ?", (charge_id,))

async def check_address_balance(charge_id: str) -> List[Charges]:
    charge = await get_charge(charge_id)
    if charge.onchainaddress:
        mempool = await get_mempool(charge.user)
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(mempool.endpoint + "/api/address/" + charge.onchainaddress)
                respAmount = r.json()['chain_stats']['funded_txo_sum']
                if (charge.balance + respAmount) >= charge.balance:
                    return await update_charge(charge_id = charge_id, balance = (charge.balance + respAmount), paid = True) 
                else:
                    return await update_charge(charge_id = charge_id, balance = (charge.balance + respAmount), paid = False) 
        except Exception:
            pass
    if charge.lnbitswallet:
        invoice_status = await check_invoice_status(charge.lnbitswallet, charge.payment_hash)
        if invoice_status.paid:
            return await update_charge(charge_id = charge_id, balance = charge.balance, paid = True) 
    row = await db.fetchone("SELECT * FROM charges WHERE id = ?", (charge_id,))
    return Charges.from_row(row) if row else None
