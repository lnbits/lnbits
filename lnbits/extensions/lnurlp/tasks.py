import aiohttp

from lnbits.core.models import Payment


async def on_invoice_paid(payment: Payment) -> None:
    islnurlp = "lnurlp" in payment.extra.get("tags", {})
    print("invoice paid on lnurlp?", islnurlp)
    if islnurlp:
        print("dispatching webhook")
        async with aiohttp.ClientSession() as session:
            await session.post("https://fiatjaf.free.beeceptor.com", json=payment)
