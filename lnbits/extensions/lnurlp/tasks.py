import trio  # type: ignore
import httpx

from lnbits.core.models import Payment
from lnbits.tasks import run_on_pseudo_request, register_invoice_listener

from .crud import mark_webhook_sent, get_pay_link


async def register_listeners():
    invoice_paid_chan_send, invoice_paid_chan_recv = trio.open_memory_channel(2)
    register_invoice_listener(invoice_paid_chan_send)
    await wait_for_paid_invoices(invoice_paid_chan_recv)


async def wait_for_paid_invoices(invoice_paid_chan: trio.MemoryReceiveChannel):
    async for payment in invoice_paid_chan:
        await run_on_pseudo_request(on_invoice_paid, payment)


async def on_invoice_paid(payment: Payment) -> None:
    if "lnurlp" != payment.extra.get("tag"):
        # not an lnurlp invoice
        return

    if payment.extra.get("wh_status"):
        # this webhook has already been sent
        return

    pay_link = get_pay_link(payment.extra.get("link", -1))
    if pay_link and pay_link.webhook_url:
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(
                    pay_link.webhook_url,
                    json={
                        "payment_hash": payment.payment_hash,
                        "payment_request": payment.bolt11,
                        "amount": payment.amount,
                        "comment": payment.extra.get("comment"),
                        "lnurlp": pay_link.id,
                    },
                    timeout=40,
                )
                mark_webhook_sent(payment, r.status_code)
            except (httpx.ConnectError, httpx.RequestError):
                mark_webhook_sent(payment, -1)
