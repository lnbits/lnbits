from datetime import date, datetime
from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import events_ext, events_renderer
from .crud import get_event, get_ticket

templates = Jinja2Templates(directory="templates")


@events_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return events_renderer().TemplateResponse(
        "events/index.html", {"request": request, "user": user.dict()}
    )


@events_ext.get("/{event_id}", response_class=HTMLResponse)
async def display(request: Request, event_id):
    event = await get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Event does not exist."
        )

    if event.amount_tickets < 1:
        return events_renderer().TemplateResponse(
            "events/error.html",
            {
                "request": request,
                "event_name": event.name,
                "event_error": "Sorry, tickets are sold out :(",
            },
        )
    datetime_object = datetime.strptime(event.closing_date, "%Y-%m-%d").date()
    if date.today() > datetime_object:
        return events_renderer().TemplateResponse(
            "events/error.html",
            {
                "request": request,
                "event_name": event.name,
                "event_error": "Sorry, ticket closing date has passed :(",
            },
        )

    return events_renderer().TemplateResponse(
        "events/display.html",
        {
            "request": request,
            "event_id": event_id,
            "event_name": event.name,
            "event_info": event.info,
            "event_price": event.price_per_ticket,
        },
    )


@events_ext.get("/ticket/{ticket_id}", response_class=HTMLResponse)
async def ticket(request: Request, ticket_id):
    ticket = await get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Ticket does not exist."
        )

    event = await get_event(ticket.event)
    if not event:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Event does not exist."
        )

    return events_renderer().TemplateResponse(
        "events/ticket.html",
        {
            "request": request,
            "ticket_id": ticket_id,
            "ticket_name": event.name,
            "ticket_info": event.info,
        },
    )


@events_ext.get("/register/{event_id}", response_class=HTMLResponse)
async def register(request: Request, event_id):
    event = await get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Event does not exist."
        )

    return events_renderer().TemplateResponse(
        "events/register.html",
        {
            "request": request,
            "event_id": event_id,
            "event_name": event.name,
            "wallet_id": event.wallet,
        },
    )
