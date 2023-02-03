import asyncio

from cashu.core.migrations import migrate_databases
from cashu.mint import migrations

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener

from . import db, ledger


async def startup_cashu_mint():
    await migrate_databases(db, migrations)
    await ledger.load_used_proofs()
    await ledger.init_keysets(autosave=False)


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "cashu":
        return

    return
