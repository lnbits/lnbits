import asyncio
import os
from binascii import hexlify, unhexlify
from hashlib import sha256
from typing import Awaitable, Union

import httpx
from embit import ec, script
from embit.networks import NETWORKS
from embit.transaction import SIGHASH, Transaction, TransactionInput, TransactionOutput
from loguru import logger

from lnbits.core.services import create_invoice, pay_invoice
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import BOLTZ_NETWORK, BOLTZ_URL

from .crud import update_swap_status
from .mempool import (
    get_fee_estimation,
    get_mempool_blockheight,
    get_mempool_fees,
    get_mempool_tx,
    get_mempool_tx_from_txs,
    send_onchain_tx,
    wait_for_websocket_message,
)
from .models import (
    CreateReverseSubmarineSwap,
    CreateSubmarineSwap,
    ReverseSubmarineSwap,
    SubmarineSwap,
    SwapStatus,
)
from .utils import check_balance, get_timestamp, req_wrap

net = NETWORKS[BOLTZ_NETWORK]
logger.debug(f"BOLTZ_URL: {BOLTZ_URL}")
logger.debug(f"Bitcoin Network: {net['name']}")


async def create_swap(data: CreateSubmarineSwap) -> SubmarineSwap:
    if not check_boltz_limits(data.amount):
        msg = f"Boltz - swap not in boltz limits"
        logger.warning(msg)
        raise Exception(msg)

    swap_id = urlsafe_short_hash()
    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=data.wallet,
            amount=data.amount,
            memo=f"swap of {data.amount} sats on boltz.exchange",
            extra={"tag": "boltz", "swap_id": swap_id},
        )
    except Exception as exc:
        msg = f"Boltz - create_invoice failed {str(exc)}"
        logger.error(msg)
        raise

    refund_privkey = ec.PrivateKey(os.urandom(32), True, net)
    refund_pubkey_hex = hexlify(refund_privkey.sec()).decode("UTF-8")

    res = req_wrap(
        "post",
        f"{BOLTZ_URL}/createswap",
        json={
            "type": "submarine",
            "pairId": "BTC/BTC",
            "orderSide": "sell",
            "refundPublicKey": refund_pubkey_hex,
            "invoice": payment_request,
            "referralId": "lnbits",
        },
        headers={"Content-Type": "application/json"},
    )
    res = res.json()
    logger.info(
        f"Boltz - created normal swap, boltz_id: {res['id']}. wallet: {data.wallet}"
    )
    return SubmarineSwap(
        id=swap_id,
        time=get_timestamp(),
        wallet=data.wallet,
        amount=data.amount,
        payment_hash=payment_hash,
        refund_privkey=refund_privkey.wif(net),
        refund_address=data.refund_address,
        boltz_id=res["id"],
        status="pending",
        address=res["address"],
        expected_amount=res["expectedAmount"],
        timeout_block_height=res["timeoutBlockHeight"],
        bip21=res["bip21"],
        redeem_script=res["redeemScript"],
    )


"""
explanation taken from electrum
send on Lightning, receive on-chain
- User generates preimage, RHASH. Sends RHASH to server.
- Server creates an LN invoice for RHASH.
- User pays LN invoice - except server needs to hold the HTLC as preimage is unknown.
- Server creates on-chain output locked to RHASH.
- User spends on-chain output, revealing preimage.
- Server fulfills HTLC using preimage.
Note: expected_onchain_amount_sat is BEFORE deducting the on-chain claim tx fee.
"""


async def create_reverse_swap(
    data: CreateReverseSubmarineSwap,
) -> [ReverseSubmarineSwap, asyncio.Task]:
    if not check_boltz_limits(data.amount):
        msg = f"Boltz - reverse swap not in boltz limits"
        logger.warning(msg)
        raise Exception(msg)

    swap_id = urlsafe_short_hash()

    if not await check_balance(data):
        logger.error(f"Boltz - reverse swap, insufficient balance.")
        return False

    claim_privkey = ec.PrivateKey(os.urandom(32), True, net)
    claim_pubkey_hex = hexlify(claim_privkey.sec()).decode("UTF-8")
    preimage = os.urandom(32)
    preimage_hash = sha256(preimage).hexdigest()

    res = req_wrap(
        "post",
        f"{BOLTZ_URL}/createswap",
        json={
            "type": "reversesubmarine",
            "pairId": "BTC/BTC",
            "orderSide": "buy",
            "invoiceAmount": data.amount,
            "preimageHash": preimage_hash,
            "claimPublicKey": claim_pubkey_hex,
            "referralId": "lnbits",
        },
        headers={"Content-Type": "application/json"},
    )
    res = res.json()

    logger.info(
        f"Boltz - created reverse swap, boltz_id: {res['id']}. wallet: {data.wallet}"
    )

    swap = ReverseSubmarineSwap(
        id=swap_id,
        amount=data.amount,
        wallet=data.wallet,
        onchain_address=data.onchain_address,
        instant_settlement=data.instant_settlement,
        claim_privkey=claim_privkey.wif(net),
        preimage=preimage.hex(),
        status="pending",
        boltz_id=res["id"],
        timeout_block_height=res["timeoutBlockHeight"],
        lockup_address=res["lockupAddress"],
        onchain_amount=res["onchainAmount"],
        redeem_script=res["redeemScript"],
        invoice=res["invoice"],
        time=get_timestamp(),
    )
    logger.debug(f"Boltz - waiting for onchain tx, reverse swap_id: {swap.id}")
    task = create_task_log_exception(
        swap.id, wait_for_onchain_tx(swap, swap_websocket_callback_initial)
    )
    return swap, task


def start_onchain_listener(swap: ReverseSubmarineSwap) -> asyncio.Task:
    return create_task_log_exception(
        swap.id, wait_for_onchain_tx(swap, swap_websocket_callback_restart)
    )


async def start_confirmation_listener(
    swap: ReverseSubmarineSwap, mempool_lockup_tx
) -> asyncio.Task:
    logger.debug(f"Boltz - reverse swap, waiting for confirmation...")

    tx, txid, *_ = mempool_lockup_tx

    confirmed = await wait_for_websocket_message({"track-tx": txid}, "txConfirmed")
    if confirmed:
        logger.debug(f"Boltz - reverse swap lockup transaction confirmed! claiming...")
        await create_claim_tx(swap, mempool_lockup_tx)
    else:
        logger.debug(f"Boltz - reverse swap lockup transaction still not confirmed.")


def create_task_log_exception(swap_id: str, awaitable: Awaitable) -> asyncio.Task:
    async def _log_exception(awaitable):
        try:
            return await awaitable
        except Exception as e:
            logger.error(f"Boltz - reverse swap failed!: {swap_id} - {e}")
            await update_swap_status(swap_id, "failed")

    return asyncio.create_task(_log_exception(awaitable))


async def swap_websocket_callback_initial(swap):
    wstask = asyncio.create_task(
        wait_for_websocket_message(
            {"track-address": swap.lockup_address}, "address-transactions"
        )
    )
    logger.debug(
        f"Boltz - created task, waiting on mempool websocket for address: {swap.lockup_address}"
    )

    # create_task is used because pay_invoice is stuck as long as boltz does not
    # see the onchain claim tx and it ends up in deadlock
    task: asyncio.Task = create_task_log_exception(
        swap.id,
        pay_invoice(
            wallet_id=swap.wallet,
            payment_request=swap.invoice,
            description=f"reverse swap for {swap.amount} sats on boltz.exchange",
            extra={"tag": "boltz", "swap_id": swap.id, "reverse": True},
        ),
    )
    logger.debug(f"Boltz - task pay_invoice created, reverse swap_id: {swap.id}")

    done, pending = await asyncio.wait(
        [task, wstask], return_when=asyncio.FIRST_COMPLETED
    )
    message = done.pop().result()

    # pay_invoice already failed, do not wait for onchain tx anymore
    if message is None:
        logger.debug(f"Boltz - pay_invoice already failed cancel websocket task.")
        wstask.cancel()
        raise

    return task, message


async def swap_websocket_callback_restart(swap):
    logger.debug(f"Boltz - swap_websocket_callback_restart called...")
    message = await wait_for_websocket_message(
        {"track-address": swap.lockup_address}, "address-transactions"
    )
    return None, message


async def wait_for_onchain_tx(swap: ReverseSubmarineSwap, callback):
    task, txs = await callback(swap)
    mempool_lockup_tx = get_mempool_tx_from_txs(txs, swap.lockup_address)
    if mempool_lockup_tx:
        tx, txid, *_ = mempool_lockup_tx
        if swap.instant_settlement or tx["status"]["confirmed"]:
            logger.debug(
                f"Boltz - reverse swap instant settlement, claiming immediatly..."
            )
            await create_claim_tx(swap, mempool_lockup_tx)
        else:
            await start_confirmation_listener(swap, mempool_lockup_tx)
        try:
            if task:
                await task
        except:
            logger.error(
                f"Boltz - could not await pay_invoice task, but sent onchain. should never happen!"
            )
    else:
        logger.error(f"Boltz - mempool lockup tx not found.")


async def create_claim_tx(swap: ReverseSubmarineSwap, mempool_lockup_tx):
    tx = await create_onchain_tx(swap, mempool_lockup_tx)
    await send_onchain_tx(tx)
    logger.debug(f"Boltz - onchain tx sent, reverse swap completed")
    await update_swap_status(swap.id, "complete")


async def create_refund_tx(swap: SubmarineSwap):
    mempool_lockup_tx = get_mempool_tx(swap.address)
    tx = await create_onchain_tx(swap, mempool_lockup_tx)
    await send_onchain_tx(tx)


def check_block_height(block_height: int):
    current_block_height = get_mempool_blockheight()
    if current_block_height <= block_height:
        msg = f"refund not possible, timeout_block_height ({block_height}) is not yet exceeded ({current_block_height})"
        logger.debug(msg)
        raise Exception(msg)


"""
a submarine swap consists of 2 onchain tx's a lockup and a redeem tx.
we create a tx to redeem the funds locked by the onchain lockup tx.
claim tx for reverse swaps, refund tx for normal swaps they are the same
onchain redeem tx, the difference between them is the private key, onchain_address,
input sequence and input script_sig
"""


async def create_onchain_tx(
    swap: Union[ReverseSubmarineSwap, SubmarineSwap], mempool_lockup_tx
) -> Transaction:
    is_refund_tx = type(swap) == SubmarineSwap
    if is_refund_tx:
        check_block_height(swap.timeout_block_height)
        privkey = ec.PrivateKey.from_wif(swap.refund_privkey)
        onchain_address = swap.refund_address
        preimage = b""
        sequence = 0xFFFFFFFE
    else:
        privkey = ec.PrivateKey.from_wif(swap.claim_privkey)
        preimage = unhexlify(swap.preimage)
        onchain_address = swap.onchain_address
        sequence = 0xFFFFFFFF

    locktime = swap.timeout_block_height
    redeem_script = unhexlify(swap.redeem_script)

    fees = get_fee_estimation()

    tx, txid, vout_cnt, vout_amount = mempool_lockup_tx

    script_pubkey = script.address_to_scriptpubkey(onchain_address)

    vin = [TransactionInput(unhexlify(txid), vout_cnt, sequence=sequence)]
    vout = [TransactionOutput(vout_amount - fees, script_pubkey)]
    tx = Transaction(vin=vin, vout=vout)

    if is_refund_tx:
        tx.locktime = locktime

    # TODO: 2 rounds for fee calculation, look at vbytes after signing and do another TX
    s = script.Script(data=redeem_script)
    for i, inp in enumerate(vin):
        if is_refund_tx:
            rs = bytes([34]) + bytes([0]) + bytes([32]) + sha256(redeem_script).digest()
            tx.vin[i].script_sig = script.Script(data=rs)
        h = tx.sighash_segwit(i, s, vout_amount)
        sig = privkey.sign(h).serialize() + bytes([SIGHASH.ALL])
        witness_items = [sig, preimage, redeem_script]
        tx.vin[i].witness = script.Witness(items=witness_items)

    return tx


def get_swap_status(swap: Union[SubmarineSwap, ReverseSubmarineSwap]) -> SwapStatus:
    swap_status = SwapStatus(
        wallet=swap.wallet,
        swap_id=swap.id,
    )

    try:
        boltz_request = get_boltz_status(swap.boltz_id)
        swap_status.boltz = boltz_request["status"]
    except httpx.HTTPStatusError as exc:
        json = exc.response.json()
        swap_status.boltz = json["error"]
        if "could not find" in swap_status.boltz:
            swap_status.exists = False

    if type(swap) == SubmarineSwap:
        swap_status.reverse = False
        swap_status.address = swap.address
    else:
        swap_status.reverse = True
        swap_status.address = swap.lockup_address

    swap_status.block_height = get_mempool_blockheight()
    swap_status.timeout_block_height = (
        f"{str(swap.timeout_block_height)} -> current: {str(swap_status.block_height)}"
    )

    if swap_status.block_height >= swap.timeout_block_height:
        swap_status.hit_timeout = True

    mempool_tx = get_mempool_tx(swap_status.address)
    swap_status.lockup = mempool_tx
    if mempool_tx == None:
        swap_status.has_lockup = False
        swap_status.confirmed = False
        swap_status.mempool = "transaction.unknown"
        swap_status.message = "lockup tx not in mempool"
    else:
        swap_status.has_lockup = True
        tx, *_ = mempool_tx
        if tx["status"]["confirmed"] == True:
            swap_status.mempool = "transaction.confirmed"
            swap_status.confirmed = True
        else:
            swap_status.confirmed = False
            swap_status.mempool = "transaction.unconfirmed"

    return swap_status


def check_boltz_limits(amount):
    try:
        pairs = get_boltz_pairs()
        limits = pairs["pairs"]["BTC/BTC"]["limits"]
        return amount >= limits["minimal"] and amount <= limits["maximal"]
    except:
        return False


def get_boltz_pairs():
    res = req_wrap(
        "get",
        f"{BOLTZ_URL}/getpairs",
        headers={"Content-Type": "application/json"},
    )
    return res.json()


def get_boltz_status(boltzid):
    res = req_wrap(
        "post",
        f"{BOLTZ_URL}/swapstatus",
        json={"id": boltzid},
    )
    return res.json()
