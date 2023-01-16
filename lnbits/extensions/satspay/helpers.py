import httpx
from loguru import logger

from .models import Charges


def public_charge(charge: Charges):
    c = {
        "id": charge.id,
        "description": charge.description,
        "onchainaddress": charge.onchainaddress,
        "payment_request": charge.payment_request,
        "payment_hash": charge.payment_hash,
        "time": charge.time,
        "amount": charge.amount,
        "balance": charge.balance,
        "paid": charge.paid,
        "timestamp": charge.timestamp,
        "time_elapsed": charge.time_elapsed,
        "time_left": charge.time_left,
        "paid": charge.paid,
        "custom_css": charge.custom_css,
    }

    if charge.paid:
        c["completelink"] = charge.completelink
        c["completelinktext"] = charge.completelinktext

    return c


async def call_webhook(charge: Charges):
    async with httpx.AsyncClient() as client:
        try:
            assert charge.webhook
            r = await client.post(
                charge.webhook,
                json=public_charge(charge),
                timeout=40,
            )
            return {
                "webhook_success": r.is_success,
                "webhook_message": r.reason_phrase,
                "webhook_response": r.text,
            }
        except Exception as e:
            logger.warning(f"Failed to call webhook for charge {charge.id}")
            logger.warning(e)
            return {"webhook_success": False, "webhook_message": str(e)}


async def fetch_onchain_balance(charge: Charges):
    endpoint = (
        f"{charge.config.mempool_endpoint}/testnet"
        if charge.config.network == "Testnet"
        else charge.config.mempool_endpoint
    )
    assert endpoint
    assert charge.onchainaddress
    async with httpx.AsyncClient() as client:
        r = await client.get(endpoint + "/api/address/" + charge.onchainaddress)
        return r.json()["chain_stats"]["funded_txo_sum"]
