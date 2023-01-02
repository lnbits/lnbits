import asyncio
import time
from typing import Awaitable, List, Optional, Union

from boltz_client.boltz import BoltzSwapResponse
from loguru import logger

from lnbits.core.services import pay_invoice
from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import (
    AutoReverseSubmarineSwap,
    CreateAutoReverseSubmarineSwap,
    CreateReverseSubmarineSwap,
    CreateSubmarineSwap,
    ReverseSubmarineSwap,
    SubmarineSwap,
)
from .utils import create_boltz_client


async def get_submarine_swaps(wallet_ids: Union[str, List[str]]) -> List[SubmarineSwap]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM boltz.submarineswap WHERE wallet IN ({q}) order by time DESC",
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
            "pending",
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
    data: CreateReverseSubmarineSwap,
) -> ReverseSubmarineSwap:

    client = create_boltz_client()
    claim_privkey_wif, preimage_hex, swap = client.create_reverse_swap(
        amount=data.amount
    )
    swap_id = urlsafe_short_hash()

    reverse_swap = ReverseSubmarineSwap(
        id=swap_id,
        wallet=data.wallet,
        status="pending",
        boltz_id=swap.id,
        instant_settlement=data.instant_settlement,
        preimage=preimage_hex,
        claim_privkey=claim_privkey_wif,
        lockup_address=swap.lockupAddress,
        invoice=swap.invoice,
        onchain_amount=swap.onchainAmount,
        onchain_address=data.onchain_address,
        timeout_block_height=swap.timeoutBlockHeight,
        redeem_script=swap.redeemScript,
        amount=data.amount,
        time=int(time.time()),
    )

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
            reverse_swap.id,
            reverse_swap.wallet,
            reverse_swap.status,
            reverse_swap.boltz_id,
            reverse_swap.instant_settlement,
            reverse_swap.preimage,
            reverse_swap.claim_privkey,
            reverse_swap.lockup_address,
            reverse_swap.invoice,
            reverse_swap.onchain_amount,
            reverse_swap.onchain_address,
            reverse_swap.timeout_block_height,
            reverse_swap.redeem_script,
            reverse_swap.amount,
        ),
    )

    claim_task = asyncio.create_task(
        client.claim_reverse_swap(
            privkey_wif=claim_privkey_wif,
            preimage_hex=preimage_hex,
            lockup_address=swap.lockupAddress,
            receive_address=data.onchain_address,
            redeem_script_hex=swap.redeemScript,
        )
    )

    pay_task = pay_invoice_and_update_status(
        swap_id,
        claim_task,
        pay_invoice(
            wallet_id=data.wallet,
            payment_request=swap.invoice,
            description=f"reverse swap for {swap.onchainAmount} sats on boltz.exchange",
            extra={"tag": "boltz", "swap_id": swap_id, "reverse": True},
        ),
    )

    asyncio.gather(claim_task, pay_task)

    return reverse_swap


def pay_invoice_and_update_status(
    swap_id: str, wstask: asyncio.Task, awaitable: Awaitable
) -> asyncio.Task:
    async def _pay_invoice(awaitable):
        try:
            awaited = await awaitable
            await update_swap_status(swap_id, "complete")
            return awaited
        except asyncio.exceptions.CancelledError:
            """lnbits process was exited, do nothing and handle it in startup script"""
        except:
            wstask.cancel()
            await update_swap_status(swap_id, "failed")

    return asyncio.create_task(_pay_invoice(awaitable))


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


async def get_auto_reverse_submarine_swap_by_wallet(
    wallet_id,
) -> Optional[AutoReverseSubmarineSwap]:
    row = await db.fetchone(
        "SELECT * FROM boltz.auto_reverse_submarineswap WHERE wallet = ?", (wallet_id,)
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
            onchain_address,
            instant_settlement,
            balance,
            amount
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            swap_id,
            swap.wallet,
            swap.onchain_address,
            swap.instant_settlement,
            swap.balance,
            swap.amount,
        ),
    )
    return await get_auto_reverse_submarine_swap(swap_id)


async def delete_auto_reverse_submarine_swap(swap_id):
    await db.execute(
        "DELETE FROM boltz.auto_reverse_submarineswap WHERE id = ?", (swap_id,)
    )


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
