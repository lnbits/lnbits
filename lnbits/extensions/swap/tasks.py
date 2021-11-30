import asyncio

import httpx

from lnbits.core.crud import get_wallet
from lnbits.core.models import Payment
from lnbits.extensions.swap.crud import create_swapout, get_recurrent_swapout_by_wallet
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
    has_recurrent = await get_recurrent_swapout_by_wallet(payment.wallet_id)
    
    if has_recurrent:
        # do the balance check
        wallet = await get_wallet(wallet_id=payment.wallet_id)
        assert wallet
        if wallet.balance_msat < (has_recurrent.threshold * 1000):
            return

        data = {
            "wallet": has_recurrent.wallet,
            "onchainwallet": has_recurrent.onchainwallet,
            "onchainaddress": has_recurrent.onchainaddress,
            "amount": has_recurrent.threshold,
            "recurrent": True,
            "fee": has_recurrent.fee,
        }
        
        await create_swapout(CreateSwapOut(**data))
