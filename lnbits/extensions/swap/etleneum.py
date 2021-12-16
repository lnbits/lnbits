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


async def get_contract_state():
    url = (
        URL
        + f"/~/contract/{CONTRACT}/state"
    )
    response = None
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                url,
                headers={"Content-Type": "application/json"},
            )
            response = resp.json()
        except AssertionError:
            response = "Error occured"
    return response


async def contract_call_method(method, payload = {}, amount = 0, session = ""):
    # Create a call to etleneum
    url = (
        URL
        + f"/~/contract/{CONTRACT}/call?session={session}"
    )
    response = None
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "method": method,
                    "payload": payload,
                    "msatoshi": amount * 1000
                    },
                timeout=40,
            )
            response = resp.json()
        except AssertionError:
            response = "Error occured"
    return response
