import asyncio
import datetime
from http import HTTPStatus
from urllib.parse import urlparse

from fastapi import HTTPException
from loguru import logger
from starlette.requests import Request
from starlette.responses import HTMLResponse

from lnbits import bolt11

from .. import core_app
from ..crud import get_standalone_payment
from ..tasks import api_invoice_listeners


@core_app.get("/.well-known/lnurlp/{username}")
async def lnaddress(username: str, request: Request):
    from lnbits.extensions.lnaddress.lnurl import lnurl_response

    domain = urlparse(str(request.url)).netloc
    return await lnurl_response(username, domain, request)


@core_app.get("/public/v1/payment/{payment_hash}")
async def api_public_payment_longpolling(payment_hash):
    payment = await get_standalone_payment(payment_hash)

    if not payment:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Payment does not exist."
        )
    elif not payment.pending:
        return {"status": "paid"}

    try:
        invoice = bolt11.decode(payment.bolt11)
        expiration = datetime.datetime.fromtimestamp(invoice.date + invoice.expiry)
        if expiration < datetime.datetime.now():
            return {"status": "expired"}
    except:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Invalid bolt11 invoice."
        )

    payment_queue = asyncio.Queue(0)

    logger.debug(f"adding standalone invoice listener for hash: {payment_hash}")
    api_invoice_listeners[payment_hash] = payment_queue

    response = None

    async def payment_info_receiver(cancel_scope):
        async for payment in payment_queue.get():
            if payment.payment_hash == payment_hash:
                nonlocal response
                response = {"status": "paid"}
                cancel_scope.cancel()

    async def timeouter(cancel_scope):
        await asyncio.sleep(45)
        cancel_scope.cancel()

    asyncio.create_task(payment_info_receiver())
    asyncio.create_task(timeouter())

    if response:
        return response
    else:
        raise HTTPException(status_code=HTTPStatus.REQUEST_TIMEOUT, detail="timeout")
