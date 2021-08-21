from quart import g, abort, render_template
from datetime import date, datetime
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import events_ext
from .crud import get_ticket, get_event
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@events_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    return templates.TemplateResponse("events/index.html", {"user":g.user})

@events_ext.route("/<event_id>")
async def display(request: Request, event_id):
    event = await get_event(event_id)
    if not event:
        abort(HTTPStatus.NOT_FOUND, "Event does not exist.")

    if event.amount_tickets < 1:
        return await templates.TemplateResponse(
            "events/error.html",
            {"request":request,
            "event_name":event.name,
            "event_error":"Sorry, tickets are sold out :("}
        )
    datetime_object = datetime.strptime(event.closing_date, "%Y-%m-%d").date()
    if date.today() > datetime_object:
        return await templates.TemplateResponse(
            "events/error.html",
            {"request":request,
            "event_name":event.name,
            "event_error":"Sorry, ticket closing date has passed :("}
        )

    return await templates.TemplateResponse(
        "events/display.html",
        {"request":request,
        "event_id":event_id,
        "event_name":event.name,
        "event_info":event.info,
        "event_price":event.price_per_ticket}
    )


@events_ext.route("/ticket/<ticket_id>")
async def ticket(request: Request, ticket_id):
    ticket = await get_ticket(ticket_id)
    if not ticket:
        abort(HTTPStatus.NOT_FOUND, "Ticket does not exist.")

    event = await get_event(ticket.event)
    if not event:
        abort(HTTPStatus.NOT_FOUND, "Event does not exist.")

    return await templates.TemplateResponse(
        "events/ticket.html",
        {"request":request,
        "ticket_id":ticket_id,
        "ticket_name":event.name,
        "ticket_info":event.info}
    )


@events_ext.route("/register/<event_id>")
async def register(request: Request, event_id):
    event = await get_event(event_id)
    if not event:
        abort(HTTPStatus.NOT_FOUND, "Event does not exist.")

    return await templates.TemplateResponse(
        "events/register.html",
        {"request":request,
        "event_id":event_id,
        "event_name":event.name,
        "wallet_id":event.wallet}
    )
