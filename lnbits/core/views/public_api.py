import asyncio
from http import HTTPStatus

from fastapi import APIRouter, HTTPException
from loguru import logger

from lnbits import bolt11

from ..crud import get_standalone_payment
from ..tasks import api_invoice_listeners

public_router = APIRouter(tags=["Core"])


@public_router.get("/public/v1/payment/{payment_hash}")
async def api_public_payment_longpolling(payment_hash):
    payment = await get_standalone_payment(payment_hash)

    if not payment:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Payment does not exist."
        )
    # TODO: refactor to use PaymentState
    if payment.success:
        return {"status": "paid"}

    try:
        invoice = bolt11.decode(payment.bolt11)
        if invoice.has_expired():
            return {"status": "expired"}
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Invalid bolt11 invoice."
        ) from exc

    payment_queue = asyncio.Queue(0)

    logger.debug(f"adding standalone invoice listener for hash: {payment_hash}")
    api_invoice_listeners[payment_hash] = payment_queue

    response = None

    async def payment_info_receiver():
        for payment in await payment_queue.get():
            if payment.payment_hash == payment_hash:
                nonlocal response
                response = {"status": "paid"}

    async def timeouter(cancel_scope):
        await asyncio.sleep(45)
        cancel_scope.cancel()

    cancel_scope = asyncio.create_task(payment_info_receiver())
    asyncio.create_task(timeouter(cancel_scope))  # noqa: RUF006

    if response:
        return response
    else:
        raise HTTPException(status_code=HTTPStatus.REQUEST_TIMEOUT, detail="timeout")
