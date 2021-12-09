import asyncio
import json
import httpx

from lnbits.core import db as core_db
from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener
from lnbits.core.views.api import api_wallet

from .crud import get_lnurlpayout, get_lnurlpayout_from_wallet


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    try:
        # Check its got a payout associated with it
        lnurlpayout_link = await get_lnurlpayout_from_wallet(payment.wallet_id)
        print(lnurlpayout_link)
        if lnurlpayout_link:
            # Check the wallet balance is more than the threshold
            wallet = await api_wallet(payment.wallet_id)
            if wallet.balance + (wallet.balance/100*2) < lnurlpayout_link.threshold:
                return
            # Get the invoice from the LNURL to pay
            async with httpx.AsyncClient() as client:
                try:
                    url = await api_payments_decode({"data": data.lnurlpay})
                    if str(url["domain"])[0:4] != "http":
                        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="LNURL broken")
                    try:
                        r = await client.get(
                            str(url["domain"]),
                            timeout=40,
                        )
                        res = r.json()
                        print(res)
                        print(res["callback"])
                        try:
                            r = await client.get(
                                res["callback"] + "?amount=" + (lnurlpayout_link.threshold * 1000),
                                timeout=40,
                            )
                            res = r.json()
                            print(res["pr"])
                            await api_payments_pay_invoice(res["pr"], payment.wallet_id)
                        except:
                            return
                    except (httpx.ConnectError, httpx.RequestError):
                        return
                except Exception:
                    raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Failed to save LNURLPayout")
    except:
        return