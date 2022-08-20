import asyncio
import calendar
import datetime
import json
import os
from binascii import hexlify, unhexlify
from hashlib import sha256
from http import HTTPStatus
from typing import Union

import httpx
from embit import ec, script
from embit.networks import NETWORKS
from embit.transaction import SIGHASH, Transaction, TransactionInput, TransactionOutput
from loguru import logger
from websockets import connect

from lnbits import bolt11
from lnbits.core.services import (
    check_invoice_status,
    create_invoice,
    create_payment,
    delete_payment,
    fee_reserve,
    get_wallet,
    pay_invoice,
)
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import DEBUG

from .crud import update_swap_status
from .models import (
    CreateReverseSubmarineSwap,
    CreateSubmarineSwap,
    ReverseSubmarineSwap,
    SubmarineSwap,
)

# if DEBUG:
net = NETWORKS["regtest"]
BOLTZ_URL = "http://127.0.0.1:9001"
MEMPOOL_SPACE_URL = "http://127.0.0.1:8080"
MEMPOOL_SPACE_URL_WS = "ws://127.0.0.1:8080"
# else:
#     net = NETWORKS["main"]
#     BOLTZ_URL = "https://boltz.exchange/api"
#     MEMPOOL_SPACE_URL = "https://mempool.space"
#     MEMPOOL_SPACE_URL_WS = "wss://mempool.space"

logger.debug(f"MEMPOOL_SPACE_URL: {MEMPOOL_SPACE_URL}")
logger.debug(f"BOLTZ_URL: {BOLTZ_URL}")
logger.debug(f"Bitcoin Network: {net['name']}")


def get_swap_status(swap):
    status = ""
    can_refund = False
    try:
        boltz_request = get_boltz_status(swap.boltz_id)
        boltz_status = boltz_request["status"]
    except:
        boltz_status = "boltz is offline"
    if type(swap) == SubmarineSwap:
        address = swap.address
    else:
        address = swap.lockup_address

    mempool_status = get_mempool_tx_status(address)
    block_height = get_mempool_blockheight()

    if block_height >= swap.timeout_block_height:
        can_refund = True
        status += "hit timeout_block_height"
    else:
        status += "timeout_block_height not exceeded "

    if mempool_status == "transaction.unknown":
        can_refund = False
        status += ", lockup_tx not in mempool"

    if can_refund == True:
        status += ", refund is possible"

    timeout_block_height = f"{str(swap.timeout_block_height)} -> {str(block_height)}"

    return {
        "wallet": swap.wallet,
        "status": status,
        "swap_id": swap.id,
        "boltz": boltz_status,
        "mempool": mempool_status,
        "timeout_block_height": timeout_block_height,
    }


async def create_reverse_swap(
    data: CreateReverseSubmarineSwap,
) -> [ReverseSubmarineSwap, asyncio.Task]:
    """explanation taken from electrum
    send on Lightning, receive on-chain
    - User generates preimage, RHASH. Sends RHASH to server.
    - Server creates an LN invoice for RHASH.
    - User pays LN invoice - except server needs to hold the HTLC as preimage is unknown.
    - Server creates on-chain output locked to RHASH.
    - User spends on-chain output, revealing preimage.
    - Server fulfills HTLC using preimage.
    Note: expected_onchain_amount_sat is BEFORE deducting the on-chain claim tx fee.
    """

    swap_id = urlsafe_short_hash()

    # check if we can pay the invoice before we create the actual swap on boltz
    amount_msat = data.amount * 1000
    fee_reserve_msat = fee_reserve(amount_msat)
    wallet = await get_wallet(data.wallet)
    assert wallet
    if wallet.balance_msat - fee_reserve_msat < amount_msat:
        logger.error(
            f"Boltz - reverse swap, insufficient balance. this should never be called before checking: {wallet.balance_msat} msat"
        )
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
        time=get_timestamp(),
    )

    logger.debug(f"Boltz - waiting for onchain tx, reverse swap_id: {swap.id}")
    return swap, asyncio.create_task(wait_for_onchain_tx(swap, res["invoice"]))


async def wait_for_onchain_tx(swap: ReverseSubmarineSwap, invoice):
    async with connect(f"{MEMPOOL_SPACE_URL_WS}/api/v1/ws") as websocket:
        logger.debug(f"Boltz - mempool websocket connected... waiting for onchain tx")
        await websocket.send(json.dumps({"track-address": swap.lockup_address}))

        # create_task is used because pay_invoice is stuck as long as boltz does not
        # see the onchain claim tx and it ends up in deadlock
        task = asyncio.create_task(
            pay_invoice(
                wallet_id=swap.wallet,
                payment_request=invoice,
                description=f"reverse submarine swap for {swap.amount} sats on boltz.exchange",
                extra={"tag": "boltz", "swap_id": swap.id, "reverse": True},
            )
        )
        logger.debug(f"Boltz - task pay_invoice created, reverse swap_id: {swap.id}")

        data = await websocket.recv()
        logger.debug(f"Boltz - awaited mempool websocket")
        message = json.loads(data)

        try:
            txs = message["address-transactions"]
        except IndexError as e:
            logger.error("Boltz - index error in mempool address-transactions")
            raise Exception("no txs in mempool")

        mempool_lockup_tx = get_mempool_tx_from_txs(txs, swap.lockup_address)
        if mempool_lockup_tx:
            tx = await create_onchain_tx(swap, mempool_lockup_tx)
            await send_onchain_tx(tx)
            try:
                await task
                logger.debug(
                    f"Boltz - awaited pay_invoice task, reverse swap completed"
                )
                await update_swap_status(swap, "complete")
            except:
                logger.error(
                    f"Boltz - could not await pay_invoice task, reverse swap failed"
                )
                await update_swap_status(swap, "failed")
        else:
            logger.error(f"Boltz - mempool lockup tx not found.")


async def create_refund_tx(swap: SubmarineSwap):
    mempool_lockup_tx = get_mempool_tx(swap.address)
    tx = await create_onchain_tx(swap, mempool_lockup_tx)
    await send_onchain_tx(tx)


def get_mempool_tx_status(address):
    mempool_tx = get_mempool_tx(address)
    if mempool_tx == None:
        status = "transaction.unknown"
    else:
        tx, *_ = get_mempool_tx(address)
        if tx["status"]["confirmed"] == True:
            status = "transaction.confirmed"
        else:
            status = "transaction.unconfirmed"
    return status


def get_mempool_tx(address):
    res = req_wrap(
        "get",
        f"{MEMPOOL_SPACE_URL}/api/address/{address}/txs",
        headers={"Content-Type": "text/plain"},
    )
    txs = json.loads(res.text)
    return get_mempool_tx_from_txs(txs, address)


def get_mempool_tx_from_txs(txs, address):
    if len(txs) == 0:
        return None
    tx, txid, vout_cnt, vout_amount = None
    for i, a_tx in enumerate(txs):
        for vout in a_tx["vout"]:
            if vout["scriptpubkey_address"] == address:
                tx = a_tx
                txid = a_tx["txid"]
                vout_cnt = i
                vout_amount = vout["value"]
    # should never happen
    if tx == None:
        raise Exception("mempool tx not found")
    if txid == None:
        raise Exception("mempool txid not found")
    return tx, txid, vout_cnt, vout_amount


# send on on-chain, receive lightning
async def create_swap(data: CreateSubmarineSwap) -> SubmarineSwap:
    swap_id = urlsafe_short_hash()
    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=data.wallet,
            amount=data.amount,
            memo=f"submarine swap of {data.amount} sats on boltz.exchange",
            extra={"tag": "boltz", "swap_id": swap_id},
        )
    except Exception as e:
        msg = "Boltz swap create_invoice failed"
        logger.error(msg)
        raise Exception(msg)

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


def get_fee_estimation() -> int:
    # TODO: hardcoded maximum tx size, in the future we try to get the size of the tx via embit
    # we need a function like Transaction.vsize()
    tx_size_vbyte = 200
    mempool_fees = get_mempool_fees()
    return mempool_fees * tx_size_vbyte


# a submarine swap consists of 2 onchain tx's a lockup and a redeem tx.
# we create a tx to redeem the funds locked by the onchain lockup tx.
# claim tx for reverse swaps, refund tx for normal swaps they are the same
# onchain redeem tx, the difference between them is the private key, onchain_address,
# input sequence and input script_sig
async def create_onchain_tx(
    swap: Union[ReverseSubmarineSwap, SubmarineSwap], mempool_lockup_tx
) -> Transaction:

    is_refund_tx = type(swap) == SubmarineSwap
    if is_refund_tx:
        current_block_height = get_mempool_blockheight()
        if current_block_height <= swap.timeout_block_height:
            msg = f"refund not possible, timeout_block_height ({swap.timeout_block_height}) is not yet exceeded ({current_block_height})"
            logger.debug(msg)
            raise Exception(msg)
        privkey = ec.PrivateKey.from_wif(swap.refund_privkey)
        onchain_address = swap.refund_address
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
    for i in range(len(vin)):
        inp = vin[i]
        if is_refund_tx:
            #    OP_PUSHDATA34     OP_0     OP_PUSHDATA35
            rs = bytes([34]) + bytes([0]) + bytes([32]) + sha256(redeem_script).digest()
            tx.vin[i].script_sig = script.Script(data=rs)
        h = tx.sighash_segwit(i, s, vout_amount)
        sig = privkey.sign(h).serialize() + bytes([SIGHASH.ALL])
        witness_items = [sig, preimage, redeem_script]
        tx.vin[i].witness = script.Witness(items=witness_items)

    return tx


def get_timestamp():
    date = datetime.datetime.utcnow()
    return calendar.timegm(date.utctimetuple())


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


def get_mempool_fees() -> int:
    res = req_wrap(
        "get",
        f"{MEMPOOL_SPACE_URL}/api/v1/fees/recommended",
        headers={"Content-Type": "text/plain"},
    )
    return int(res.text)


def get_mempool_blockheight() -> int:
    res = req_wrap(
        "get",
        f"{MEMPOOL_SPACE_URL}/api/blocks/tip/height",
        headers={"Content-Type": "text/plain"},
    )
    return int(res.text)


async def send_onchain_tx(tx: Transaction):
    res = req_wrap(
        "post",
        f"{MEMPOOL_SPACE_URL}/api/tx",
        headers={"Content-Type": "text/plain"},
        data=hexlify(tx.serialize()),
    )
    return res.json()


def req_wrap(funcname, *args, **kwargs):
    try:
        try:
            func = getattr(httpx, funcname)
        except AttributeError:
            logger.error('httpx function not found "%s"' % funcname)
        else:
            res = func(*args, timeout=30, **kwargs)
        res.raise_for_status()
        return res
    except httpx.RequestError as exc:
        msg = f"Unreachable: {exc.request.url!r}."
        logger.error(msg)
        raise Exception(msg)
    except httpx.HTTPStatusError as exc:
        msg = f"HTTP Status Error: {exc.response.status_code} while requesting {exc.request.url!r}."
        logger.error(msg)
        raise Exception(msg)
