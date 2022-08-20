from http import HTTPStatus
from typing import List, Optional, Union

from starlette.exceptions import HTTPException

from .boltz import (
    create_swap,
    create_reverse_swap,
)
from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import (
    CreateSubmarineSwap,
    SubmarineSwap,
    CreateReverseSubmarineSwap,
    ReverseSubmarineSwap,
)

"""
Submarine Swaps
"""
async def get_submarine_swaps(wallet_ids: Union[str, List[str]]) -> List[SubmarineSwap]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM boltz.submarineswap WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [SubmarineSwap(**row) for row in rows]

async def get_submarine_swap(swap_id) -> SubmarineSwap:
    row = await db.fetchone("SELECT * FROM boltz.submarineswap WHERE id = ?", (swap_id,))
    return SubmarineSwap(**row) if row else None

async def create_submarine_swap(data: CreateSubmarineSwap) -> Optional[SubmarineSwap]:

    swap_id = urlsafe_short_hash()
    swap = await create_swap(swap_id, data)
    await db.execute(
        """
        INSERT INTO boltz.submarineswap (
            id,
            wallet,
            boltz_id,
            refund_privkey,
            expected_amount,
            timeout_block_height,
            address,
            bip21,
            redeem_script,
            amount
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            swap_id,
            swap.wallet,
            swap.boltz_id,
            swap.refund_privkey,
            swap.expected_amount,
            swap.timeout_block_height,
            swap.address,
            swap.bip21,
            swap.redeem_script,
            swap.amount
        )
    )
    return await get_submarine_swap(swap_id)

async def delete_submarine_swap(swap_id):
    await db.execute("DELETE FROM boltz.submarineswap WHERE id = ?", (swap_id,))



"""
Reverse Submarine Swaps
"""
async def get_reverse_submarine_swaps(wallet_ids: Union[str, List[str]]) -> List[ReverseSubmarineSwap]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM boltz.reverse_submarineswap WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [ReverseSubmarineSwap(**row) for row in rows]

async def get_reverse_submarine_swap(swap_id) -> SubmarineSwap:
    row = await db.fetchone("SELECT * FROM boltz.reverse_submarineswap WHERE id = ?", (swap_id,))
    return ReverseSubmarineSwap(**row) if row else None

async def create_reverse_submarine_swap(data: CreateReverseSubmarineSwap) -> Optional[ReverseSubmarineSwap]:

    swap_id = urlsafe_short_hash()
    swap = await create_reverse_swap(swap_id, data)
    await db.execute(
        """
        INSERT INTO boltz.reverse_submarineswap (
            id,
            wallet,
            boltz_id,
            instant_settlement,
            preimage,
            claim_privkey,
            lockup_address,
            onchain_amount,
            onchain_address,
            timeout_block_height,
            redeem_script,
            amount
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            swap_id,
            swap.wallet,
            swap.boltz_id,
            swap.instant_settlement,
            swap.preimage,
            swap.claim_privkey,
            swap.lockup_address,
            swap.onchain_amount,
            swap.onchain_address,
            swap.timeout_block_height,
            swap.redeem_script,
            swap.amount
        )
    )
    return await get_reverse_submarine_swap(swap_id)

async def delete_reverse_submarine_swap(swap_id):
    await db.execute("DELETE FROM boltz.reverse_submarineswap WHERE id = ?", (swap_id,))
