from http import HTTPStatus
from typing import List, Optional, Union

from starlette.exceptions import HTTPException

from lnbits.core.services import pay_invoice
from lnbits.extensions.swap.etleneum import create_queue_pay
from lnbits.extensions.watchonly.crud import get_fresh_address
from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import (
    CreateRecurrent,
    CreateSwapIn,
    CreateSwapOut,
    Recurrent,
    SwapIn,
    SwapOut,
)


#SWAP OUT
async def get_swapouts(wallet_ids: Union[str, List[str]]) -> List[SwapOut]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM swap.out WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [SwapOut(**row) for row in rows]

async def get_swapout(swap_id) -> SwapOut:
    row = await db.fetchone("SELECT * FROM swap.out WHERE id = ?", (swap_id,))
    return SwapOut(**row) if row else None

async def create_swapout(data: CreateSwapOut) -> Optional[SwapOut]:
    if data.onchainwallet:
        onchain = await get_fresh_address(data.onchainwallet)
        onchainaddress = onchain.address
    else:
        onchainaddress = data.onchainaddress
    
    
    etl_resp = await create_queue_pay(data.amount, onchainaddress, data.fee)
    # print("ETL", etl_resp)    
    invoice = etl_resp["value"].get("invoice")
    
    try:
        await pay_invoice(
            wallet_id=data.wallet,
            payment_request=invoice,
            extra={"tag": "swapout"},
        )
    except:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Payment failed")

    swap_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO swap.out (
            id,
            wallet,
            onchainwallet,
            onchainaddress,
            amount,
            recurrent,
            fee
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            swap_id,
            data.wallet,
            data.onchainwallet,
            onchainaddress,
            data.amount,
            data.recurrent,
            data.fee
        )
    )
    return await get_swapout(swap_id)


async def delete_swapout(swap_id):
    await db.execute("DELETE FROM swap.out WHERE id = ?", (swap_id,))

## RECURRENT SWAP OUT

async def get_recurrents(wallet_ids: Union[str, List[str]]) -> List[Recurrent]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM swap.recurrent WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Recurrent(**row) for row in rows]

async def create_recurrent(data: CreateRecurrent):
    if data.onchainwallet:
        onchainaddress = f"Watch-only wallet {data.onchainwallet}."
    else:
        onchainaddress = data.onchainaddress
    swap_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO swap.recurrent (
            id,
            wallet,
            onchainwallet,
            onchainaddress,
            threshold,
            fee
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            swap_id,
            data.wallet,
            data.onchainwallet,
            onchainaddress,
            data.threshold,
            data.fee
        )
    )
    return await get_recurrent_swapout(swap_id)

async def update_recurrent(swap_id: str, **kwargs) -> Optional[Recurrent]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE swap.recurrent SET {q} WHERE id = ?", (*kwargs.values(), swap_id)
    )
    row = await db.fetchone("SELECT * FROM swap.recurrent WHERE id = ?", (swap_id,))
    return Recurrent(**row) if row else None

async def delete_recurrent(swap_id):
    await db.execute("DELETE FROM swap.recurrent WHERE id = ?", (swap_id,))


async def get_recurrent_swapout(swap_id) -> Optional[Recurrent]:
    row = await db.fetchone(
        "SELECT * from swap.recurrent WHERE id = ?",
        (swap_id,),
    )
    return Recurrent(**row) if row else None

async def get_recurrent_swapout_by_wallet(wallet_id) -> Optional[Recurrent]:
    row = await db.fetchone(
        "SELECT * from swap.recurrent WHERE wallet = ?",
        (wallet_id,),
    )
    return Recurrent(**row) if row else None


async def unique_recurrent_swapout(wallet_id):
    row, = await db.fetchone(
        "SELECT COUNT(wallet) FROM swap.recurrent WHERE wallet = ?",
        (wallet_id,),
    )
    return row


#SWAP IN
async def get_swapins(wallet_ids: Union[str, List[str]]) -> List[SwapIn]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM swap.in WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [SwapIn(**row) for row in rows]

async def get_swap_in(swap_id) -> Optional[SwapIn]:
    row = await db.fetchone(
        "SELECT * from swap.in WHERE id = ?",
        (swap_id,),
    )
    return SwapIn(**row) if row else None

async def create_swap_in(data: CreateSwapIn):
    swap_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO swap.in (
            id,
            wallet,
            session_id,
            reserve_id,
            amount
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            swap_id,
            data.wallet,
            data.session_id,
            data.reserve_id,
            data.amount
        )
    )

    return await get_swap_in(swap_id)

async def update_swap_in(swap_id: str, **kwargs) -> SwapIn:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE swap.in SET {q} WHERE id = ?", (*kwargs.values(), swap_id)
    )
    row = await db.fetchone("SELECT * FROM swap.in WHERE id = ?", (swap_id,))
    assert row, "Updated swap in couldn't be retrieved"
    print("ROW", SwapIn(**row))
    return SwapIn(**row)
