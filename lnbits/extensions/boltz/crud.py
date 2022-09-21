from http import HTTPStatus
from typing import List, Optional, Union

from loguru import logger
from starlette.exceptions import HTTPException

from . import db
from .models import (
    AutoReverseSubmarineSwap,
    CreateAutoReverseSubmarineSwap,
    CreateReverseSubmarineSwap,
    CreateSubmarineSwap,
    ReverseSubmarineSwap,
    SubmarineSwap,
)


async def get_submarine_swaps(wallet_ids: Union[str, List[str]]) -> List[SubmarineSwap]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM boltz.submarineswap WHERE wallet IN ({q}) order by time DESC",
        (*wallet_ids,),
    )

    return [SubmarineSwap(**row) for row in rows]


async def get_pending_submarine_swaps(
    wallet_ids: Union[str, List[str]]
) -> List[SubmarineSwap]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM boltz.submarineswap WHERE wallet IN ({q}) and status='pending' order by time DESC",
        (*wallet_ids,),
    )
    return [SubmarineSwap(**row) for row in rows]


async def get_all_pending_submarine_swaps() -> List[SubmarineSwap]:
    rows = await db.fetchall(
        f"SELECT * FROM boltz.submarineswap WHERE status='pending' order by time DESC",
    )
    return [SubmarineSwap(**row) for row in rows]


async def get_submarine_swap(swap_id) -> SubmarineSwap:
    row = await db.fetchone(
        "SELECT * FROM boltz.submarineswap WHERE id = ?", (swap_id,)
    )
    return SubmarineSwap(**row) if row else None


async def create_submarine_swap(swap: SubmarineSwap) -> Optional[SubmarineSwap]:

    await db.execute(
        """
        INSERT INTO boltz.submarineswap (
            id,
            wallet,
            payment_hash,
            status,
            boltz_id,
            refund_privkey,
            refund_address,
            expected_amount,
            timeout_block_height,
            address,
            bip21,
            redeem_script,
            amount
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            swap.id,
            swap.wallet,
            swap.payment_hash,
            swap.status,
            swap.boltz_id,
            swap.refund_privkey,
            swap.refund_address,
            swap.expected_amount,
            swap.timeout_block_height,
            swap.address,
            swap.bip21,
            swap.redeem_script,
            swap.amount,
        ),
    )
    return await get_submarine_swap(swap.id)


async def delete_submarine_swap(swap_id):
    await db.execute("DELETE FROM boltz.submarineswap WHERE id = ?", (swap_id,))


async def get_reverse_submarine_swaps(
    wallet_ids: Union[str, List[str]]
) -> List[ReverseSubmarineSwap]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM boltz.reverse_submarineswap WHERE wallet IN ({q}) order by time DESC",
        (*wallet_ids,),
    )

    return [ReverseSubmarineSwap(**row) for row in rows]


async def get_pending_reverse_submarine_swaps(
    wallet_ids: Union[str, List[str]]
) -> List[ReverseSubmarineSwap]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM boltz.reverse_submarineswap WHERE wallet IN ({q}) and status='pending' order by time DESC",
        (*wallet_ids,),
    )

    return [ReverseSubmarineSwap(**row) for row in rows]


async def get_all_pending_reverse_submarine_swaps() -> List[ReverseSubmarineSwap]:
    rows = await db.fetchall(
        f"SELECT * FROM boltz.reverse_submarineswap WHERE status='pending' order by time DESC"
    )

    return [ReverseSubmarineSwap(**row) for row in rows]


async def get_reverse_submarine_swap(swap_id) -> ReverseSubmarineSwap:
    row = await db.fetchone(
        "SELECT * FROM boltz.reverse_submarineswap WHERE id = ?", (swap_id,)
    )
    return ReverseSubmarineSwap(**row) if row else None


async def create_reverse_submarine_swap(
    swap: ReverseSubmarineSwap,
) -> Optional[ReverseSubmarineSwap]:

    await db.execute(
        """
        INSERT INTO boltz.reverse_submarineswap (
            id,
            wallet,
            status,
            boltz_id,
            instant_settlement,
            preimage,
            claim_privkey,
            lockup_address,
            invoice,
            onchain_amount,
            onchain_address,
            timeout_block_height,
            redeem_script,
            amount
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            swap.id,
            swap.wallet,
            swap.status,
            swap.boltz_id,
            swap.instant_settlement,
            swap.preimage,
            swap.claim_privkey,
            swap.lockup_address,
            swap.invoice,
            swap.onchain_amount,
            swap.onchain_address,
            swap.timeout_block_height,
            swap.redeem_script,
            swap.amount,
        ),
    )
    return await get_reverse_submarine_swap(swap.id)


async def get_auto_reverse_submarine_swaps(
    wallet_ids: Union[str, List[str]]
) -> List[AutoReverseSubmarineSwap]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM boltz.auto_reverse_submarineswap WHERE wallet IN ({q}) order by time DESC",
        (*wallet_ids,),
    )

    return [AutoReverseSubmarineSwap(**row) for row in rows]


async def get_auto_reverse_submarine_swap(swap_id) -> AutoReverseSubmarineSwap:
    row = await db.fetchone(
        "SELECT * FROM boltz.auto_reverse_submarineswap WHERE id = ?", (swap_id,)
    )
    return AutoReverseSubmarineSwap(**row) if row else None


async def create_auto_reverse_submarine_swap(
    swap: AutoReverseSubmarineSwap,
) -> Optional[AutoReverseSubmarineSwap]:

    await db.execute(
        """
        INSERT INTO boltz.auto_reverse_submarineswap (
            id,
            wallet,
            status,
            instant_settlement,
            threshold,
            amount
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            swap.id,
            swap.wallet,
            swap.status,
            swap.instant_settlement,
            swap.threshold,
            swap.amount,
        ),
    )
    return await get_auto_reverse_submarine_swap(swap.id)


async def update_swap_status(swap_id: str, status: str):

    reverse = ""
    swap = await get_submarine_swap(swap_id)
    if swap is None:
        swap = await get_reverse_submarine_swap(swap_id)

    if swap is None:
        return None

    if type(swap) == SubmarineSwap:
        await db.execute(
            "UPDATE boltz.submarineswap SET status='"
            + status
            + "' WHERE id='"
            + swap.id
            + "'"
        )
    if type(swap) == ReverseSubmarineSwap:
        reverse = "reverse"
        await db.execute(
            "UPDATE boltz.reverse_submarineswap SET status='"
            + status
            + "' WHERE id='"
            + swap.id
            + "'"
        )

    message = f"Boltz - {reverse} swap status change: {status}. boltz_id: {swap.boltz_id}, wallet: {swap.wallet}"
    logger.info(message)

    return swap
