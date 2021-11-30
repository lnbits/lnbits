import asyncio

import httpx

from lnbits.core.crud import get_wallet
from lnbits.core.models import Payment
from lnbits.core.views.generic import wallet
from lnbits.extensions.swap.crud import create_swapout, get_recurrent_swapout
from lnbits.extensions.swap.models import CreateSwapOut
from lnbits.tasks import register_invoice_listener

# from .crud import get_address, get_domain, set_address_paid, set_address_renewed


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    has_recurrent = await get_recurrent_swapout(payment.wallet_id)
    print("TASK#1", has_recurrent)
    if has_recurrent:
        # do the balance check
        wallet = await get_wallet(wallet_id=payment.wallet_id)
        assert wallet
        if wallet.balance_msat < (has_recurrent.amount * 1000):
            return
        data = CreateSwapOut(
            has_recurrent.wallet,
            has_recurrent.onchainwallet,
            has_recurrent.onchainaddress,
            has_recurrent.amount,
            has_recurrent.recurrent,
            has_recurrent.fee
        )
        print("TASK#2", data)
        await create_swapout(data=data)
