import os
import asyncio
import json
import httpx
import calendar
import datetime
from starlette.exceptions import HTTPException
from http import HTTPStatus
from lnbits import bolt11
from websockets import connect
from typing import Union
from embit import ec, script
from embit.networks import NETWORKS
from embit.transaction import Transaction, TransactionInput, TransactionOutput, SIGHASH
from binascii import unhexlify, hexlify
from lnbits.helpers import urlsafe_short_hash

from hashlib import sha256

from lnbits.core.services import (
    get_wallet,
    fee_reserve,
    check_invoice_status,
    create_invoice,
    create_payment,
    delete_payment,
    pay_invoice,
)

from .crud import update_swap_status

from .models import (
    CreateSubmarineSwap,
    SubmarineSwap,
    CreateReverseSubmarineSwap,
    ReverseSubmarineSwap,
)

from lnbits.settings import DEBUG

if DEBUG:
    net = NETWORKS["regtest"]
    BOLTZ_URL = "http://boltz:9001"
    MEMPOOL_SPACE_URL = "http://mempool-web:8080"
    MEMPOOL_SPACE_URL_WS = "ws://mempool-web:8080"
else:
    net = NETWORKS["main"]
    BOLTZ_URL = "https://boltz.exchange/api"
    MEMPOOL_SPACE_URL = "https://mempool.space"
    MEMPOOL_SPACE_URL_WS = "wss://mempool.space"


def get_boltz_pairs():
    return create_get_request(BOLTZ_URL + "/getpairs")


def get_boltz_status(boltzid):
    return create_post_request(
        BOLTZ_URL + "/swapstatus",
        {
            "id": boltzid,
        },
    )


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

    return {
        "wallet": swap.wallet,
        "status": status,
        "swap_id": swap.id,
        "boltz": boltz_status,
        "mempool": mempool_status,
        "timeout_block_height": str(swap.timeout_block_height)
        + " -> "
        + str(block_height),
    }


def get_mempool_fees() -> int:
    res = httpx.get(
        MEMPOOL_SPACE_URL + "/api/v1/fees/recommended",
        headers={"Content-Type": "text/plain"},
        timeout=40,
    )
    handle_request_errors(res)
    data = json.loads(res.text)
    try:
        value = int(data["hourFee"])
    except ValueError:
        msg = "get_mempool_fees: " + data["hourFee"] + " value is not an integer"
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=msg)

    return value


def get_mempool_blockheight() -> int:
    res = httpx.get(
        MEMPOOL_SPACE_URL + "/api/blocks/tip/height",
        headers={"Content-Type": "text/plain"},
        timeout=40,
    )
    handle_request_errors(res)
    try:
        value = int(res.text)
    except ValueError:
        msg = "get_mempool_blockheight: " + res.text + " value is not an integer"
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=msg)
    return value


async def create_reverse_swap(data: CreateReverseSubmarineSwap):
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
        raise HTTPException(
            status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail="Insufficient balance."
        )

    claim_privkey = ec.PrivateKey(os.urandom(32), True, net)
    claim_pubkey_hex = hexlify(claim_privkey.sec()).decode("UTF-8")
    preimage = os.urandom(32)
    preimage_hash = sha256(preimage).hexdigest()

    res = create_post_request(
        BOLTZ_URL + "/createswap",
        {
            "type": "reversesubmarine",
            "pairId": "BTC/BTC",
            "orderSide": "buy",
            "invoiceAmount": data.amount,
            "preimageHash": preimage_hash,
            "claimPublicKey": claim_pubkey_hex,
        },
    )

    # check payment again with real invoice after we created a swap
    # to include fee reserve calculation
    # try:
    #     await check_balance(wallet, data.amount, res)
    # except Exception as e:
    #     raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

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
        time=getTimestamp(),
    )

    asyncio.create_task(wait_for_onchain_tx(swap, res["invoice"]))
    return swap


async def wait_for_onchain_tx(swap: ReverseSubmarineSwap, invoice):
    uri = MEMPOOL_SPACE_URL_WS + f"/api/v1/ws"
    async with connect(uri) as websocket:
        await websocket.send(json.dumps({"track-address": swap.lockup_address}))

        # create_task is used because pay_invoice is stuck as long as boltz does not
        # see the onchain claim tx and it ends up in deadlock
        task = asyncio.create_task(pay_invoice(
           wallet_id=swap.wallet,
           payment_request=invoice,
           description=f"reverse submarine swap for {swap.amount} sats on boltz.exchange",
           extra={"tag": "boltz", "swap_id": swap.id, "reverse": True},
        ))

        data = await websocket.recv()
        message = json.loads(data)

        try:
            txs = message["address-transactions"]
        except IndexError as e:
            print("index error in mempool address-transactions")
            print(repr(e))
            return
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="no txs in mempool"
            )

        mempool_lockup_tx = get_mempool_tx_from_txs(txs, swap.lockup_address)
        if mempool_lockup_tx:
            tx = await create_onchain_tx(swap, mempool_lockup_tx)
            await send_onchain_tx(tx)
            try:
                await task
                await update_swap_status(swap, "complete")
            except:
                await update_swap_status(swap, "failed")


async def create_refund_tx(swap: SubmarineSwap):
    mempool_lockup_tx = get_mempool_tx(swap.address)
    tx = await create_onchain_tx(swap, mempool_lockup_tx)
    await send_onchain_tx(tx)


def get_mempool_tx_status(address):
    mempool_tx = get_mempool_tx(address)
    if mempool_tx == None:
        status = "transaction.unknown"
    else:
        tx, _, _, _ = get_mempool_tx(address)
        if tx["status"]["confirmed"] == True:
            status = "transaction.confirmed"
        else:
            status = "transaction.unconfirmed"
    return status


def get_mempool_tx(address):
    res = httpx.get(
        MEMPOOL_SPACE_URL + "/api/address/" + address + "/txs",
        headers={"Content-Type": "text/plain"},
        timeout=40,
    )
    handle_request_errors(res)
    txs = json.loads(res.text)
    return get_mempool_tx_from_txs(txs, address)


def get_mempool_tx_from_txs(txs, address):
    if len(txs) == 0:
        return None
    tx = None
    txid = None
    vout_cnt = None
    vout_amount = None
    for a_tx in txs:
        i = 0
        for vout in a_tx["vout"]:
            if vout["scriptpubkey_address"] == address:
                tx = a_tx
                txid = a_tx["txid"]
                vout_cnt = i
                vout_amount = vout["value"]
            i += 1
    # should never happen
    if tx == None:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="tx not found"
        )
    if txid == None:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="txid not found"
        )
    if vout_cnt == None:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="vout_cnt not found"
        )
    return tx, txid, vout_cnt, vout_amount


async def send_onchain_tx(tx: Transaction):
    res = httpx.post(
        MEMPOOL_SPACE_URL + "/api/tx",
        headers={"Content-Type": "text/plain"},
        data=hexlify(tx.serialize()),
        timeout=40,
    )
    handle_request_errors(res)
    return res


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
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    refund_privkey = ec.PrivateKey(os.urandom(32), True, net)
    refund_pubkey_hex = hexlify(refund_privkey.sec()).decode("UTF-8")

    res = create_post_request(
        BOLTZ_URL + "/createswap",
        {
            "type": "submarine",
            "pairId": "BTC/BTC",
            "orderSide": "sell",
            "refundPublicKey": refund_pubkey_hex,
            "invoice": payment_request,
        },
    )
    return SubmarineSwap(
        id=swap_id,
        time=getTimestamp(),
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
    # hardcoded maximum tx size, in the future we try to get the size of the tx via embit (not possible yet)
    tx_size_vbyte = 200
    mempool_fees = get_mempool_fees()
    return mempool_fees * tx_size_vbyte


# claim tx for reverse swaps
# refund tx for normal swaps
async def create_onchain_tx(
    swap: Union[ReverseSubmarineSwap, SubmarineSwap], mempool_lockup_tx
) -> Transaction:

    if type(swap) == SubmarineSwap:
        current_block_height = get_mempool_blockheight()
        if current_block_height <= swap.timeout_block_height:
            msg = f"refund not possible, timeout_block_height ({swap.timeout_block_height}) is not yet exceeded ({current_block_height})"
            raise HTTPException(status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail=msg)
        privkey = ec.PrivateKey.from_wif(swap.refund_privkey)
        preimage = b""
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

    if type(swap) == SubmarineSwap:
        tx.locktime = locktime

    # TODO: 2 rounds for fee calculation, look at vbytes after signing and do another TX
    s = script.Script(data=redeem_script)
    for i in range(len(vin)):
        inp = vin[i]
        if type(swap) == SubmarineSwap:
            # OP_0 == 0
            # OP_PUSHDATA34 == 34
            # OP_PUSHDATA35 == 35
            rs = bytes([34]) + bytes([0]) + bytes([32]) + sha256(redeem_script).digest()
            tx.vin[i].script_sig = script.Script(data=rs)
        h = tx.sighash_segwit(i, s, vout_amount)
        sig = privkey.sign(h).serialize() + bytes([SIGHASH.ALL])
        witness_items = [sig, preimage, redeem_script]
        tx.vin[i].witness = script.Witness(items=witness_items)

    return tx


def getTimestamp():
    date = datetime.datetime.utcnow()
    return calendar.timegm(date.utctimetuple())


def create_post_request(url, payload={}):
    payload["referralId"] = "lnbits"
    res = httpx.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=40,
    )
    handle_request_errors(res)
    return res.json()


def create_get_request(url):
    res = httpx.get(
        url,
        headers={"Content-Type": "application/json"},
        timeout=40,
    )
    handle_request_errors(res)
    return res.json()


def handle_request_errors(res):
    try:
        res.raise_for_status()
    except httpx.HTTPStatusError as exc:
        content = exc.response.content.decode("UTF-8")
        if content:
            content = f" Content: {content}"
        msg = f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.{content}"
        raise HTTPException(status_code=exc.response.status_code, detail=msg)


# async def check_balance(wallet, amount, res):
#     invoice = bolt11.decode(res["invoice"])
#     amount_msat = amount * 1000
#     fee_reserve_msat = fee_reserve(amount_msat)
#     temp_id = f"temp_{urlsafe_short_hash()}"

#     # create a temporary payment here so we can check if
#     # the balance is enough in the next step
#     async with db.connect() as conn:
#         await create_payment(
#             checking_id=temp_id,
#             fee=-fee_reserve_msat,
#             conn=conn,
#             wallet_id=wallet.id,
#             payment_hash=invoice.payment_hash,
#             payment_request=res["invoice"],
#             amount=-amount_msat,
#             memo="swap-test-payment-"+temp_id
#         )

#         wallet = await get_wallet(wallet.id)
#         assert wallet

#         # first check if we can pay the invoice
#         if wallet.balance_msat <= 0:
#             if wallet.balance_msat > -fee_reserve_msat:
#                 raise HTTPException(
#                     status_code=HTTPStatus.METHOD_NOT_ALLOWED,
#                     detail=f"You must reserve at least 1% ({round(fee_reserve_msat/1000)} sat) to cover potential routing fees."
#                 )
#             raise HTTPException(
#                 status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail="Insufficient balance."
#             )
#         await delete_payment(temp_id, conn=conn)
