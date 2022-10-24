import asyncio
from http import HTTPStatus

import httpx
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core import db as core_db
from lnbits.core.crud import get_wallet
from lnbits.core.models import Payment
from lnbits.core.services import pay_invoice
from lnbits.core.views.api import api_payments_decode
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_lnurlpayout_from_wallet


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    try:
        # Check its got a payout associated with it
        lnurlpayout_link = await get_lnurlpayout_from_wallet(payment.wallet_id)
        logger.debug("LNURLpayout", lnurlpayout_link)
        if lnurlpayout_link:

            # Check the wallet balance is more than the threshold

            wallet = await get_wallet(lnurlpayout_link.wallet)
            threshold = lnurlpayout_link.threshold + (lnurlpayout_link.threshold * 0.02)

            if wallet.balance < threshold:
                return
            # Get the invoice from the LNURL to pay
            async with httpx.AsyncClient() as client:
                try:
                    url = await api_payments_decode({"data": lnurlpayout_link.lnurlpay})
                    if str(url["domain"])[0:4] != "http":
                        raise HTTPException(
                            status_code=HTTPStatus.FORBIDDEN, detail="LNURL broken"
                        )

                    try:
                        r = await client.get(str(url["domain"]), timeout=40)
                        res = r.json()
                        try:
                            r = await client.get(
                                res["callback"]
                                + "?amount="
                                + str(
                                    int((wallet.balance - wallet.balance * 0.02) * 1000)
                                ),
                                timeout=40,
                            )
                            res = r.json()

                            if hasattr(res, "status") and res["status"] == "ERROR":
                                raise HTTPException(
                                    status_code=HTTPStatus.FORBIDDEN,
                                    detail=res["reason"],
                                )
                            try:
                                await pay_invoice(
                                    wallet_id=payment.wallet_id,
                                    payment_request=res["pr"],
                                    extra={"tag": "lnurlpayout"},
                                )
                                return
                            except:
                                pass

                        except Exception as e:
                            print("ERROR", str(e))
                            return
                    except (httpx.ConnectError, httpx.RequestError):
                        return
                except Exception:
                    raise HTTPException(
                        status_code=HTTPStatus.FORBIDDEN,
                        detail="Failed to save LNURLPayout",
                    )
    except:
        return
