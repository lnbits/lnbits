import asyncio
import json
from binascii import hexlify

import httpx
import websockets
from embit.transaction import Transaction
from loguru import logger

from lnbits.settings import BOLTZ_MEMPOOL_SPACE_URL, BOLTZ_MEMPOOL_SPACE_URL_WS

from .utils import req_wrap

logger.debug(f"BOLTZ_MEMPOOL_SPACE_URL: {BOLTZ_MEMPOOL_SPACE_URL}")
logger.debug(f"BOLTZ_MEMPOOL_SPACE_URL_WS: {BOLTZ_MEMPOOL_SPACE_URL_WS}")

websocket_url = f"{BOLTZ_MEMPOOL_SPACE_URL_WS}/api/v1/ws"


async def wait_for_websocket_message(send, message_string):
    async for websocket in websockets.connect(websocket_url):
        try:
            await websocket.send(json.dumps({"action": "want", "data": ["blocks"]}))
            await websocket.send(json.dumps(send))
            async for raw in websocket:
                message = json.loads(raw)
                if message_string in message:
                    return message.get(message_string)
        except websockets.ConnectionClosed:
            continue


def get_mempool_tx(address):
    res = req_wrap(
        "get",
        f"{BOLTZ_MEMPOOL_SPACE_URL}/api/address/{address}/txs",
        headers={"Content-Type": "text/plain"},
    )
    txs = res.json()
    return get_mempool_tx_from_txs(txs, address)


def get_mempool_tx_from_txs(txs, address):
    if len(txs) == 0:
        return None
    tx = txid = vout_cnt = vout_amount = None
    for a_tx in txs:
        for i, vout in enumerate(a_tx["vout"]):
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


def get_fee_estimation() -> int:
    # TODO: hardcoded maximum tx size, in the future we try to get the size of the tx via embit
    # we need a function like Transaction.vsize()
    tx_size_vbyte = 200
    mempool_fees = get_mempool_fees()
    return mempool_fees * tx_size_vbyte


def get_mempool_fees() -> int:
    res = req_wrap(
        "get",
        f"{BOLTZ_MEMPOOL_SPACE_URL}/api/v1/fees/recommended",
        headers={"Content-Type": "text/plain"},
    )
    fees = res.json()
    return int(fees["economyFee"])


def get_mempool_blockheight() -> int:
    res = req_wrap(
        "get",
        f"{BOLTZ_MEMPOOL_SPACE_URL}/api/blocks/tip/height",
        headers={"Content-Type": "text/plain"},
    )
    return int(res.text)


async def send_onchain_tx(tx: Transaction):
    raw = hexlify(tx.serialize())
    logger.debug(f"Boltz - mempool sending onchain tx...")
    req_wrap(
        "post",
        f"{BOLTZ_MEMPOOL_SPACE_URL}/api/tx",
        headers={"Content-Type": "text/plain"},
        content=raw,
    )
