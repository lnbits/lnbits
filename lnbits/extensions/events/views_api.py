from quart import g, jsonify, request
from http import HTTPStatus

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from fastapi.encoders import jsonable_encoder
from fastapi import Query
from pydantic import BaseModel

from . import events_ext
from .crud import (
    create_ticket,
    set_ticket_paid,
    get_ticket,
    get_tickets,
    delete_ticket,
    create_event,
    update_event,
    get_event,
    get_events,
    delete_event,
    get_event_tickets,
    reg_ticket,
)


# Events



@events_ext.get("/api/v1/events")
@api_check_wallet_key("invoice")
async def api_events():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        [event._asdict() for event in await get_events(wallet_ids)],
        HTTPStatus.OK,
    )

class CreateData(BaseModel):
    wallet:  str = Query(...)
    name:  str = Query(...)
    info:  str = Query(...)
    closing_date:  str = Query(...)
    event_start_date:  str = Query(...)
    event_end_date:  str = Query(...)
    amount_tickets:  int = Query(..., ge=0)
    price_per_ticket:  int = Query(..., ge=0)

@events_ext.post("/api/v1/events")
@events_ext.put("/api/v1/events/{event_id}")
@api_check_wallet_key("invoice")
async def api_event_create(data: CreateData, event_id=None):
    if event_id:
        event = await get_event(event_id)
        if not event:
            return {"message": "Form does not exist."}, HTTPStatus.NOT_FOUND

        if event.wallet != g.wallet.id:
            return {"message": "Not your event."}, HTTPStatus.FORBIDDEN

        event = await update_event(event_id, **data)
    else:
        event = await create_event(**data)

    return event._asdict(), HTTPStatus.CREATED


@events_ext.delete("/api/v1/events/{event_id}")
@api_check_wallet_key("invoice")
async def api_form_delete(event_id):
    event = await get_event(event_id)
    if not event:
        return {"message": "Event does not exist."}, HTTPStatus.NOT_FOUND

    if event.wallet != g.wallet.id:
        return {"message": "Not your event."}, HTTPStatus.FORBIDDEN

    await delete_event(event_id)
    return "", HTTPStatus.NO_CONTENT


#########Tickets##########


@events_ext.get("/api/v1/tickets")
@api_check_wallet_key("invoice")
async def api_tickets():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        [ticket._asdict() for ticket in await get_tickets(wallet_ids)],
        HTTPStatus.OK,
    )

class CreateTicketData(BaseModel):
    name:  str = Query(...)
    email:  str

@events_ext.post("/api/v1/tickets/{event_id}/{sats}")
async def api_ticket_make_ticket(data: CreateTicketData, event_id, sats):
    event = await get_event(event_id)
    if not event:
        return {"message": "Event does not exist."}, HTTPStatus.NOT_FOUND
    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=event.wallet,
            amount=int(sats),
            memo=f"{event_id}",
            extra={"tag": "events"},
        )
    except Exception as e:
        return {"message": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR

    ticket = await create_ticket(
        payment_hash=payment_hash, wallet=event.wallet, event=event_id, **data
    )

    if not ticket:
        return {"message": "Event could not be fetched."}, HTTPStatus.NOT_FOUND

    return {"payment_hash": payment_hash, "payment_request": payment_request}, HTTPStatus.OK


@events_ext.get("/api/v1/tickets/{payment_hash}")
async def api_ticket_send_ticket(payment_hash):
    ticket = await get_ticket(payment_hash)

    try:
        status = await check_invoice_status(ticket.wallet, payment_hash)
        is_paid = not status.pending
    except Exception:
        return {"message": "Not paid."}, HTTPStatus.NOT_FOUND

    if is_paid:
        wallet = await get_wallet(ticket.wallet)
        payment = await wallet.get_payment(payment_hash)
        await payment.set_pending(False)
        ticket = await set_ticket_paid(payment_hash=payment_hash)

        return {"paid": True, "ticket_id": ticket.id}, HTTPStatus.OK

    return {"paid": False}, HTTPStatus.OK


@events_ext.delete("/api/v1/tickets/{ticket_id}")
@api_check_wallet_key("invoice")
async def api_ticket_delete(ticket_id):
    ticket = await get_ticket(ticket_id)

    if not ticket:
        return {"message": "Ticket does not exist."}, HTTPStatus.NOT_FOUND

    if ticket.wallet != g.wallet.id:
        return {"message": "Not your ticket."}, HTTPStatus.FORBIDDEN

    await delete_ticket(ticket_id)
    return "", HTTPStatus.NO_CONTENT


# Event Tickets


@events_ext.get("/api/v1/eventtickets/{wallet_id}/{event_id]")
async def api_event_tickets(wallet_id, event_id):
    return ([ticket._asdict() for ticket in await get_event_tickets(wallet_id=wallet_id, event_id=event_id)],
        HTTPStatus.OK,
    )


@events_ext.get("/api/v1/register/ticket/{ticket_id}")
async def api_event_register_ticket(ticket_id):
    ticket = await get_ticket(ticket_id)
    if not ticket:
        return {"message": "Ticket does not exist."}, HTTPStatus.FORBIDDEN

    if not ticket.paid:
        return {"message": "Ticket not paid for."}, HTTPStatus.FORBIDDEN

    if ticket.registered == True:
        return {"message": "Ticket already registered"}, HTTPStatus.FORBIDDEN

    return [ticket._asdict() for ticket in await reg_ticket(ticket_id)], HTTPStatus.OK
