import trio  # type: ignore
from http import HTTPStatus
from typing import Optional, Tuple, List, Callable, Awaitable
from quart import Request, g
from quart_trio import QuartTrio
from werkzeug.datastructures import Headers

from lnbits.db import open_db, open_ext_db
from lnbits.settings import WALLET

from .models import Payment
from .crud import get_standalone_payment

main_app: Optional[QuartTrio] = None


def grab_app_for_later(state):
    global main_app
    main_app = state.app


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


invoice_listeners: List[Tuple[str, Callable[[Payment], Awaitable[None]]]] = []


def register_invoice_listener(ext_name: str, cb: Callable[[Payment], Awaitable[None]]):
    """
    A method intended for extensions to call when they want to be notified about
    new invoice payments incoming.
    """
    print(f"registering {ext_name} invoice_listener callback: {cb}")
    invoice_listeners.append((ext_name, cb))


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
        for ext_name, cb in invoice_listeners:
            with open_ext_db(ext_name) as g.ext_db:  # type: ignore
                await cb(payment)
