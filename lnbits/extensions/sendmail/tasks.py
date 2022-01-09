import asyncio
import httpx

from http import HTTPStatus
from starlette.exceptions import HTTPException

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener

from .crud import get_email, get_emailaddress_by_email, get_emailaddress, set_email_paid, delete_email
from .smtp import send_mail


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)
    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if "lnsendmail" != payment.extra.get("tag"):
        # not an lnurlp invoice
        return

    email = await get_email(payment.checking_id)
    if not email:
        print("this should never happen", payment)
        return

    emailaddress = await get_emailaddress(email.emailaddress_id)
    if not emailaddress:
        print("this should never happen", payment)
        return


    await payment.set_pending(False)
    await send_mail(emailaddress, email)
    await set_email_paid(payment_hash=payment.payment_hash)
