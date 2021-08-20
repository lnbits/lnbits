from quart import g, abort, render_template
from datetime import date, datetime
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import events_ext
from .crud import get_ticket, get_event


@events_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("events/index.html", user=g.user)


@events_ext.route("/<event_id>")
async def display(event_id):
    event = await get_event(event_id)
    if not event:
        abort(HTTPStatus.NOT_FOUND, "Event does not exist.")

    if event.amount_tickets < 1:
        return await render_template(
            "events/error.html",
            event_name=event.name,
            event_error="Sorry, tickets are sold out :(",
        )
    datetime_object = datetime.strptime(event.closing_date, "%Y-%m-%d").date()
    if date.today() > datetime_object:
        return await render_template(
            "events/error.html",
            event_name=event.name,
            event_error="Sorry, ticket closing date has passed :(",
        )

    return await render_template(
        "events/display.html",
        event_id=event_id,
        event_name=event.name,
        event_info=event.info,
        event_price=event.price_per_ticket,
    )


@events_ext.route("/ticket/<ticket_id>")
async def ticket(ticket_id):
    ticket = await get_ticket(ticket_id)
    if not ticket:
        abort(HTTPStatus.NOT_FOUND, "Ticket does not exist.")

    event = await get_event(ticket.event)
    if not event:
        abort(HTTPStatus.NOT_FOUND, "Event does not exist.")

    return await render_template(
        "events/ticket.html",
        ticket_id=ticket_id,
        ticket_name=event.name,
        ticket_info=event.info,
    )


@events_ext.route("/register/<event_id>")
async def register(event_id):
    event = await get_event(event_id)
    if not event:
        abort(HTTPStatus.NOT_FOUND, "Event does not exist.")

    return await render_template(
        "events/register.html",
        event_id=event_id,
        event_name=event.name,
        wallet_id=event.wallet,
    )
