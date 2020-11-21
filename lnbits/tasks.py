import trio  # type: ignore
from http import HTTPStatus
from typing import Optional, List, Callable
from quart_trio import QuartTrio

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


internal_invoice_paid, internal_invoice_received = trio.open_memory_channel(0)


async def internal_invoice_listener():
    async with trio.open_nursery() as nursery:
        async for checking_id in internal_invoice_received:
            nursery.start_soon(invoice_callback_dispatcher, checking_id)


async def invoice_listener():
    async with trio.open_nursery() as nursery:
        async for checking_id in WALLET.paid_invoices_stream():
            nursery.start_soon(invoice_callback_dispatcher, checking_id)


async def invoice_callback_dispatcher(checking_id: str):
    payment = await get_standalone_payment(checking_id)
    if payment and payment.is_in:
        await payment.set_pending(False)
        for send_chan in invoice_listeners:
            await send_chan.send(payment)
