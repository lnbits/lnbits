from typing import List, Optional, Union
from loguru import logger

from . import db
from .models import (
    AutoReverseSubmarineSwap,
    CreateAutoReverseSubmarineSwap,
    ReverseSubmarineSwap,
    CreateReverseSubmarineSwap,
    SubmarineSwap,
    CreateSubmarineSwap,
)

from boltz_client.boltz import (
    BoltzSwapResponse,
    BoltzReverseSwapResponse,
)

from lnbits.helpers import urlsafe_short_hash


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


async def get_submarine_swap(swap_id) -> Optional[SubmarineSwap]:
    row = await db.fetchone(
        "SELECT * FROM boltz.submarineswap WHERE id = ?", (swap_id,)
    )
    return SubmarineSwap(**row) if row else None


async def create_submarine_swap(
    data: CreateSubmarineSwap,
    swap: BoltzSwapResponse,
    swap_id: str,
    refund_privkey_wif: str,
    payment_hash: str,
) -> Optional[SubmarineSwap]:

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
            swap_id,
            data.wallet,
            payment_hash,
            "created",
            swap.id,
            refund_privkey_wif,
            data.refund_address,
            swap.expectedAmount,
            swap.timeoutBlockHeight,
            swap.address,
            swap.bip21,
            swap.redeemScript,
            data.amount,
        ),
    )
    return await get_submarine_swap(swap_id)


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


async def get_reverse_submarine_swap(swap_id) -> Optional[ReverseSubmarineSwap]:
    row = await db.fetchone(
        "SELECT * FROM boltz.reverse_submarineswap WHERE id = ?", (swap_id,)
    )
    return ReverseSubmarineSwap(**row) if row else None


async def create_reverse_submarine_swap(
    swap: BoltzReverseSwapResponse,
    data: CreateReverseSubmarineSwap,
    swap_id: str,
    claim_privkey_wif: str,
    preimage_hex: str,
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
            swap_id,
            data.wallet,
            "created",
            swap.id,
            data.instant_settlement,
            preimage_hex,
            claim_privkey_wif,
            swap.lockupAddress,
            swap.invoice,
            swap.onchainAmount,
            data.onchain_address,
            swap.timeoutBlockHeight,
            swap.redeemScript,
            data.amount,
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


async def get_auto_reverse_submarine_swap(
    swap_id,
) -> Optional[AutoReverseSubmarineSwap]:
    row = await db.fetchone(
        "SELECT * FROM boltz.auto_reverse_submarineswap WHERE id = ?", (swap_id,)
    )
    return AutoReverseSubmarineSwap(**row) if row else None


async def create_auto_reverse_submarine_swap(
    swap: CreateAutoReverseSubmarineSwap,
) -> Optional[AutoReverseSubmarineSwap]:

    swap_id = urlsafe_short_hash()
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
            swap_id,
            swap.wallet,
            "created",
            swap.instant_settlement,
            swap.threshold,
            swap.amount,
        ),
    )
    return await get_auto_reverse_submarine_swap(swap_id)


async def update_swap_status(swap_id: str, status: str):

    swap = await get_submarine_swap(swap_id)
    if swap:
        await db.execute(
            "UPDATE boltz.submarineswap SET status='"
            + status
            + "' WHERE id='"
            + swap.id
            + "'"
        )
        logger.info(
            f"Boltz - swap status change: {status}. boltz_id: {swap.boltz_id}, wallet: {swap.wallet}"
        )
        return swap

    reverse_swap = await get_reverse_submarine_swap(swap_id)
    if reverse_swap:
        await db.execute(
            "UPDATE boltz.reverse_submarineswap SET status='"
            + status
            + "' WHERE id='"
            + reverse_swap.id
            + "'"
        )
        logger.info(
            f"Boltz - reverse swap status change: {status}. boltz_id: {reverse_swap.boltz_id}, wallet: {reverse_swap.wallet}"
        )
        return reverse_swap

    return None
