import trio  # type: ignore
from http import HTTPStatus
from typing import Optional, List, Callable
from quart import Request, g
from quart_trio import QuartTrio
from werkzeug.datastructures import Headers

from lnbits.db import open_db
from lnbits.settings import WALLET

from lnbits.core.crud import get_standalone_payment

main_app: Optional[QuartTrio] = None


def grab_app_for_later(app: QuartTrio):
    global main_app
    main_app = app


deferred_async: List[Callable] = []


def record_async(func: Callable) -> Callable:
    def recorder(state):
        deferred_async.append(func)

    return recorder


def run_deferred_async(nursery):
    for func in deferred_async:
        nursery.start_soon(func)


async def send_push_promise(a, b) -> None:
    pass


async def run_on_pseudo_request(func: Callable, *args):
    fk = Request(
        "GET",
        "http",
        "/background/pseudo",
        b"",
        Headers([("host", "lnbits.background")]),
        "",
        "1.1",
        send_push_promise=send_push_promise,
    )
    assert main_app

    async def run():
        async with main_app.request_context(fk):
            with open_db() as g.db:  # type: ignore
                await func(*args)

    async with trio.open_nursery() as nursery:
        nursery.start_soon(run)


invoice_listeners: List[trio.MemorySendChannel] = []


def register_invoice_listener(send_chan: trio.MemorySendChannel):
    """
    A method intended for extensions to call when they want to be notified about
    new invoice payments incoming.
    """
    invoice_listeners.append(send_chan)


async def webhook_handler():
    handler = getattr(WALLET, "webhook_listener", None)
    if handler:
        return await handler()
    return "", HTTPStatus.NO_CONTENT


async def invoice_listener():
    async for checking_id in WALLET.paid_invoices_stream():
        await run_on_pseudo_request(invoice_callback_dispatcher, checking_id)


async def invoice_callback_dispatcher(checking_id: str):
    payment = get_standalone_payment(checking_id)
    if payment and payment.is_in:
        payment.set_pending(False)
        for send_chan in invoice_listeners:
            await send_chan.send(payment)
