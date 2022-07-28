from http import HTTPStatus

from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException
from starlette.requests import Request

from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.decorators import WalletTypeInfo, get_key_type
from lnbits.extensions.events.models import CreateEvent, CreateTicket

from . import events_ext
from .crud import (
    create_event,
    create_ticket,
    delete_event,
    delete_event_tickets,
    delete_ticket,
    get_event,
    get_event_tickets,
    get_events,
    get_ticket,
    get_tickets,
    reg_ticket,
    set_ticket_paid,
    update_event,
)

# Events


@events_ext.get("/api/v1/events")
async def api_events(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [event.dict() for event in await get_events(wallet_ids)]


@events_ext.post("/api/v1/events")
@events_ext.put("/api/v1/events/{event_id}")
async def api_event_create(
    data: CreateEvent, event_id=None, wallet: WalletTypeInfo = Depends(get_key_type)
):
    if event_id:
        event = await get_event(event_id)
        if not event:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail=f"Event does not exist."
            )

        if event.wallet != wallet.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail=f"Not your event."
            )
        event = await update_event(event_id, **data.dict())
    else:
        event = await create_event(data=data)

    return event.dict()


@events_ext.delete("/api/v1/events/{event_id}")
async def api_form_delete(event_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    event = await get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Event does not exist."
        )

    if event.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=f"Not your event.")

    await delete_event(event_id)
    await delete_event_tickets(event_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


#########Tickets##########


@events_ext.get("/api/v1/tickets")
async def api_tickets(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [ticket.dict() for ticket in await get_tickets(wallet_ids)]


@events_ext.get("/api/v1/tickets/{event_id}")
async def api_ticket_make_ticket(event_id):
    event = await get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Event does not exist."
        )
    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=event.wallet,
            amount=event.price_per_ticket,
            memo=f"{event_id}",
            extra={"tag": "events"},
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return {"payment_hash": payment_hash, "payment_request": payment_request}


@events_ext.post("/api/v1/tickets/{event_id}/{payment_hash}")
async def api_ticket_send_ticket(event_id, payment_hash, data: CreateTicket):
    event = await get_event(event_id)
    try:
        status = await api_payment(payment_hash)
        if status["paid"]:
            ticket = await create_ticket(
                payment_hash=payment_hash,
                wallet=event.wallet,
                event=event_id,
                name=data.name,
                email=data.email,
            )

            if not ticket:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    detail=f"Event could not be fetched.",
                )

            return {"paid": True, "ticket_id": ticket.id}
    except Exception:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not paid")
    return {"paid": False}


@events_ext.delete("/api/v1/tickets/{ticket_id}")
async def api_ticket_delete(ticket_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    ticket = await get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Ticket does not exist."
        )

    if ticket.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail=f"Not your ticket."
        )

    await delete_ticket(ticket_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


# Event Tickets


@events_ext.get("/api/v1/eventtickets/{wallet_id}/{event_id}")
async def api_event_tickets(wallet_id, event_id):
    return [
        ticket.dict()
        for ticket in await get_event_tickets(wallet_id=wallet_id, event_id=event_id)
    ]


@events_ext.get("/api/v1/register/ticket/{ticket_id}")
async def api_event_register_ticket(ticket_id):
    ticket = await get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Ticket does not exist."
        )

    if not ticket.paid:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Ticket not paid for."
        )

    if ticket.registered == True:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Ticket already registered"
        )

    return [ticket.dict() for ticket in await reg_ticket(ticket_id)]
