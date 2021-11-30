import json

import httpx

URL = "https://etleneum.com"
CONTRACT = "c8w0c13v75"

async def create_queue_pay(amount, address, fee):
    # Create a queuepay call to etleneum
    url = (
        URL
        + f"/~/contract/{CONTRACT}/call"
    )
    payload = {
        "addr": address, #onchain address
        "fee_msat": fee #fee
    }

    response = None

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "method": "queuepay",
                    "payload": payload,
                    "msatoshi": amount * 1000
                    },
                timeout=40,
            )
            response = resp.json()
        except AssertionError:
            response = "Error occured"
    return response
