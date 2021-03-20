from http import HTTPStatus
from quart.json import jsonify
import trio  # type: ignore
import httpx

from .crud import get_tournament, set_participant_paid
from lnbits.core.crud import get_user, get_wallet
from lnbits.core import db as core_db
from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener
from .challonge import challonge_add_user_to_tournament


async def register_listeners():
    invoice_paid_chan_send, invoice_paid_chan_recv = trio.open_memory_channel(2)
    register_invoice_listener(invoice_paid_chan_send)
    await wait_for_paid_invoices(invoice_paid_chan_recv)


async def wait_for_paid_invoices(invoice_paid_chan: trio.MemoryReceiveChannel):
    async for payment in invoice_paid_chan:
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if "lnchallonge" != payment.extra.get("tag"):
        # not an lnurlp invoice
        return

    await payment.set_pending(False)
    participant = await set_participant_paid(payment_hash=payment.payment_hash)
    tournament = await get_tournament(participant.tournament)

    ### Create add user to challonge tournament

    challonge_username = getattr(participant or object(), 'challonge_username', '')
    email = getattr(participant or object(), 'email', '')

    ch_response = await challonge_add_user_to_tournament(
        username=participant.username, challonge_username=challonge_username, tournament=tournament, email=email
    )

    ### Use webhook to notify about challonge user participation
    if tournament.webhook:
        async with httpx.AsyncClient() as client:
            try: # TODO
                r = await client.post(
                    tournament.webhook,
                    json={
                        "data": "data" # TODO add meaninful data to the webhook
                    },
                    timeout=40,
                )
            except AssertionError:
                webhook = None
