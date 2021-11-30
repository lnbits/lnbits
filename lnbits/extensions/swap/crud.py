from http import HTTPStatus
from typing import List, Optional, Union

from starlette.exceptions import HTTPException

from lnbits.core.services import pay_invoice
from lnbits.extensions.swap.etleneum import create_queue_pay
from lnbits.extensions.watchonly.crud import get_fresh_address
from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateSwapOut, SwapOut


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
    print("ETL", etl_resp)    
    invoice = etl_resp["value"].get("invoice")
    print(invoice, data.wallet)
    try:
        payment = await pay_invoice(
            wallet_id=data.wallet,
            payment_request=invoice,
            extra={"tag": "swapout"},
        )
        print(payment)
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

async def update_swapout() -> SwapOut:
    pass

async def get_recurrent_swapout(wallet_id) -> Optional[SwapOut]:
    row = await db.fetchone(
        "SELECT * from swap.out WHERE wallet = ? AND recurrent = ?",
        (wallet_id, True,),
    )
    return SwapOut(**row) if row else None


async def unique_recurrent_swapout(wallet_id):
    row, = await db.fetchone(
        "SELECT COUNT(wallet) FROM swap.out WHERE wallet = ? AND recurrent = ?",
        (wallet_id, True,),
    )
    return row
