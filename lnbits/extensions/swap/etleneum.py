import json

import httpx

from .models import SwapOut

URL = "https://etleneum.com"
CONTRACT = "c8w0c13v75"

async def create_queue_pay(data: SwapOut):
    # Create a queuepay call to etleneum
    url = (
        URL
        + f"/~/contract/{CONTRACT}/call"
    )
    payload = {
        "msatoshi": data.amount * 1000, #amount * 1000
        "addr": data.onchainaddress, #onchain address
        "fee_msat": data.fee #fee
    }

    response = ""

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "method": "queuepay",
                    "payload": payload,
                    "msatoshi": 0
                    },
                timeout=40,
            )
            response = resp.json()
        except AssertionError:
            response = "Error occured"
    return response
