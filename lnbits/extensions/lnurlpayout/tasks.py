import asyncio
import json
import httpx

from lnbits.core import db as core_db
from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener
from lnbits.core.api import api_wallet

from .crud import get_lnurlpayout


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    try:
        # Check its got a payout associated with it
        lnurlpayout_link = await get_lnurlpayout(payment.extra.get("link", -1))
    
        if lnurlpayout_link:
            # Check the wallet balance is more than the threshold
            wallet = api_wallet(payment.wallet_id)
            if wallet.balance < lnurlpayout_link.threshold:
                return
            # Get the invoice from the LNURL to pay
            async with httpx.AsyncClient() as client:
                try:
                    url = await api_payments_decode({"data": data.lnurlpay})
                    if str(url["domain"])[0:4] != "http":
                        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="LNURL broken")
                    try:
                        r = await client.post(
                            str(url["domain"]),
                            json={
                                "payment_hash": payment.payment_hash,
                                "payment_request": payment.bolt11,
                                "amount": payment.amount,
                                "comment": payment.extra.get("comment"),
                                "lnurlp": pay_link.id,
                            },
                            timeout=40,
                        )
                        await mark_webhook_sent(payment, r.status_code)
                    except (httpx.ConnectError, httpx.RequestError):
                        await mark_webhook_sent(payment, -1)

                except Exception:
                    raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Failed to save LNURLPayout")
    except:
        return