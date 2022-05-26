import os
import asyncio
import json
import httpx
import calendar
import datetime
from starlette.exceptions import HTTPException
from http import HTTPStatus
from sseclient import SSEClient

from websockets import connect

from typing import Union

from embit import ec, script
from embit.networks import NETWORKS
from embit.transaction import Transaction, TransactionInput, TransactionOutput, SIGHASH
from binascii import unhexlify, hexlify

from hashlib import (
    sha256
)

from lnbits.core.services import (
    check_invoice_status,
    create_invoice,
    pay_invoice
)

from .models import (
    CreateSubmarineSwap,
    SubmarineSwap,
    CreateReverseSubmarineSwap,
    ReverseSubmarineSwap,
)

net = NETWORKS['regtest']
BOLTZ_URL = "http://127.0.0.1:9001"
MEMPOOL_SPACE_URL = "http://127.0.0.1"
MEMPOOL_SPACE_URL_WS = "ws://127.0.0.1"

# net = NETWORKS['main']
# BOLTZ_URL = "https://boltz.exchange/api"
# MEMPOOL_SPACE_URL = "https://mempool.space/api"

def get_boltz_status(boltzid):
    return create_post_request(BOLTZ_URL + "/swapstatus", {
      "id": boltzid,
    })

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
        msg = 'get_mempool_fees: ' + data["hourFee"] + ' value is not an integer'
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
        msg = 'get_mempool_blockheight: ' + res.text + ' value is not an integer'
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=msg)
    return value

async def create_reverse_swap(swap_id, data: CreateReverseSubmarineSwap):
    """ explaination taken from electrum
    send on Lightning, receive on-chain
    - User generates preimage, RHASH. Sends RHASH to server.
    - Server creates an LN invoice for RHASH.
    - User pays LN invoice - except server needs to hold the HTLC as preimage is unknown.
    - Server creates on-chain output locked to RHASH.
    - User spends on-chain output, revealing preimage.
    - Server fulfills HTLC using preimage.
    Note: expected_onchain_amount_sat is BEFORE deducting the on-chain claim tx fee.
    """

    claim_privkey = ec.PrivateKey(os.urandom(32), True, net)
    claim_pubkey_hex = hexlify(claim_privkey.sec()).decode("UTF-8")
    preimage = os.urandom(32)
    preimage_hash = sha256(preimage).hexdigest()

    res = create_post_request(BOLTZ_URL + "/createswap", {
        "type": "reversesubmarine",
        "pairId": "BTC/BTC",
        "orderSide": "buy",
        "invoiceAmount": data.amount,
        "preimageHash": preimage_hash,
        "claimPublicKey": claim_pubkey_hex
    })

    swap = ReverseSubmarineSwap(
        id = swap_id,
        amount = data.amount,
        wallet = data.wallet,
        onchain_address = data.onchain_address,
        instant_settlement = data.instant_settlement,
        claim_privkey = claim_privkey.wif(net),
        preimage = preimage.hex(),
        boltz_id = res["id"],
        timeout_block_height = res["timeoutBlockHeight"],
        lockup_address = res["lockupAddress"],
        onchain_amount = res["onchainAmount"],
        redeem_script = res["redeemScript"],
        time = getTimestamp(),
    )
    asyncio.ensure_future(wait_for_onchain_tx(swap, res["invoice"]))
    return swap

async def wait_for_onchain_tx(swap: Union[ReverseSubmarineSwap, SubmarineSwap], invoice):
    uri = MEMPOOL_SPACE_URL_WS + f"/api/v1/ws"
    async with connect(uri) as websocket:
        await websocket.send(json.dumps({'track-address': swap.lockup_address }))
        # ensure_future is used because pay_invoice is stuck as long as boltz does not
        # see the onchain claim tx and it ends up in deadlock
        # TODO: what happens when payment fails?
        asyncio.ensure_future(pay_invoice(
           wallet_id=swap.wallet,
           payment_request=invoice,
           description=f"reverse submarine swap for {swap.amount} sats on boltz.exchange",
           extra={"tag": "boltz"},
        ))
        data = await websocket.recv()
        message = json.loads(data)
        mempool_lockup_tx = get_mempool_tx(message["address-transactions"], swap.lockup_address)
        tx = await create_onchain_tx(swap, mempool_lockup_tx)
        await send_onchain_tx(tx)


def get_mempool_tx(txs, address):
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
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="tx not found")
    if txid == None:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="txid not found")
    if vout_cnt == None:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="vout_cnt not found")
    return tx, txid, vout_cnt, vout_amount



async def send_onchain_tx(tx: Transaction):
    res = httpx.post(
        MEMPOOL_SPACE_URL+"/api/tx",
        headers={"Content-Type": "text/plain"},
        data=hexlify(tx.serialize()),
        timeout=40,
    )
    handle_request_errors(res)
    return res

# send on on-chain, receive lightning
async def create_swap(swap_id: str, data: CreateSubmarineSwap) -> SubmarineSwap:
    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=data.wallet,
            amount=data.amount,
            memo=f"submarine swap of {data.amount} sats on boltz.exchange",
            extra={"tag": "boltz"},
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    refund_privkey = ec.PrivateKey(os.urandom(32), True, net)
    refund_pubkey_hex = hexlify(refund_privkey.sec()).decode("UTF-8")

    res = create_post_request(BOLTZ_URL + "/createswap", {
      "type": "submarine",
      "pairId": "BTC/BTC",
      "orderSide": "sell",
      "refundPublicKey": refund_pubkey_hex,
      "invoice": payment_request
    })

    return SubmarineSwap(
        id = swap_id,
        time = getTimestamp(),
        wallet = data.wallet,
        amount = data.amount,
        refund_privkey = refund_privkey.wif(net),
        boltz_id = res["id"],
        address = res["address"],
        expected_amount = res["expectedAmount"],
        timeout_block_height = res["timeoutBlockHeight"],
        bip21 = res["bip21"],
        redeem_script = res["redeemScript"],
    )

def get_fee_estimation() -> int:
    # hardcoded maximum tx size, in the future we try to get the size of the tx via embit (not possible yet)
    tx_size_vbyte = 150
    mempool_fees = get_mempool_fees()
    return mempool_fees * tx_size_vbyte

# claim tx for reverse swaps
# refund tx for normal swaps
async def create_onchain_tx(swap: Union[ReverseSubmarineSwap, SubmarineSwap], mempool_lockup_tx) -> Transaction:

    if type(swap) == SubmarineSwap:
        current_block_height = get_mempool_blockheight()
        if current_block_height <= swap.timeout_block_height:
            msg = f"refund not possible, timeout_block_height ({swap.timeout_block_height}) is not yet exceeded ({current_block_height})"
            raise HTTPException(
                status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail=msg
            )
        privkey = ec.PrivateKey.from_wif(swap.refund_privkey)
        preimage = b""
        onchain_address = swap.address
        sequence = 0xFFFFFFFE
    else:
        privkey = ec.PrivateKey.from_wif(swap.claim_privkey)
        preimage = unhexlify(swap.preimage)
        onchain_address = swap.lockup_address
        sequence = 0xFFFFFFFF


    locktime = swap.timeout_block_height
    redeem_script = unhexlify(swap.redeem_script)

    fees = get_fee_estimation()

    tx, txid, vout_cnt, vout_amount = mempool_lockup_tx

    script_pubkey = script.address_to_scriptpubkey(onchain_address)

    vin = [TransactionInput(unhexlify(txid), vout_cnt, sequence=sequence)]
    vout = [TransactionOutput(vout_amount-fees, script_pubkey)]
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
            rs = bytes([34])+bytes([0])+bytes([32])+sha256(redeem_script).digest()
            tx.vin[i].script_sig = script.Script(data=rs)
        h = tx.sighash_segwit(i, s, vout_amount)
        sig = privkey.sign(h).serialize() + bytes([SIGHASH.ALL])
        witness_items = [ sig, preimage, redeem_script ]
        tx.vin[i].witness = script.Witness(items=witness_items)

    return tx

def getTimestamp():
    date = datetime.datetime.utcnow()
    return calendar.timegm(date.utctimetuple())

def create_post_request(url, payload = {}):
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
        raise HTTPException(
            status_code=exc.response.status_code, detail=msg
        )
