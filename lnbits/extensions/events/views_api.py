from quart import g, jsonify, request
from http import HTTPStatus

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

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


@events_ext.route("/api/v1/events", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_events():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        jsonify([event._asdict() for event in await get_events(wallet_ids)]),
        HTTPStatus.OK,
    )


@events_ext.route("/api/v1/events", methods=["POST"])
@events_ext.route("/api/v1/events/<event_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "wallet": {"type": "string", "empty": False, "required": True},
        "name": {"type": "string", "empty": False, "required": True},
        "info": {"type": "string", "min": 0, "required": True},
        "closing_date": {"type": "string", "empty": False, "required": True},
        "event_start_date": {"type": "string", "empty": False, "required": True},
        "event_end_date": {"type": "string", "empty": False, "required": True},
        "amount_tickets": {"type": "integer", "min": 0, "required": True},
        "price_per_ticket": {"type": "integer", "min": 0, "required": True},
    }
)
async def api_event_create(event_id=None):
    if event_id:
        event = await get_event(event_id)
        if not event:
            return jsonify({"message": "Form does not exist."}), HTTPStatus.NOT_FOUND

        if event.wallet != g.wallet.id:
            return jsonify({"message": "Not your event."}), HTTPStatus.FORBIDDEN

        event = await update_event(event_id, **g.data)
    else:
        event = await create_event(**g.data)

    return jsonify(event._asdict()), HTTPStatus.CREATED


@events_ext.route("/api/v1/events/<event_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_form_delete(event_id):
    event = await get_event(event_id)
    if not event:
        return jsonify({"message": "Event does not exist."}), HTTPStatus.NOT_FOUND

    if event.wallet != g.wallet.id:
        return jsonify({"message": "Not your event."}), HTTPStatus.FORBIDDEN

    await delete_event(event_id)
    return "", HTTPStatus.NO_CONTENT


#########Tickets##########


@events_ext.route("/api/v1/tickets", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_tickets():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        jsonify([ticket._asdict() for ticket in await get_tickets(wallet_ids)]),
        HTTPStatus.OK,
    )


@events_ext.route("/api/v1/tickets/<event_id>/<sats>", methods=["POST"])
@api_validate_post_request(
    schema={
        "name": {"type": "string", "empty": False, "required": True},
        "email": {"type": "string", "empty": False, "required": True},
    }
)
async def api_ticket_make_ticket(event_id, sats):
    event = await get_event(event_id)
    if not event:
        return jsonify({"message": "Event does not exist."}), HTTPStatus.NOT_FOUND
    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=event.wallet,
            amount=int(sats),
            memo=f"{event_id}",
            extra={"tag": "events"},
        )
    except Exception as e:
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    ticket = await create_ticket(
        payment_hash=payment_hash, wallet=event.wallet, event=event_id, **g.data
    )

    if not ticket:
        return jsonify({"message": "Event could not be fetched."}), HTTPStatus.NOT_FOUND

    return (
        jsonify({"payment_hash": payment_hash, "payment_request": payment_request}),
        HTTPStatus.OK,
    )


@events_ext.route("/api/v1/tickets/<payment_hash>", methods=["GET"])
async def api_ticket_send_ticket(payment_hash):
    ticket = await get_ticket(payment_hash)

    try:
        status = await check_invoice_status(ticket.wallet, payment_hash)
        is_paid = not status.pending
    except Exception:
        return jsonify({"message": "Not paid."}), HTTPStatus.NOT_FOUND

    if is_paid:
        wallet = await get_wallet(ticket.wallet)
        payment = await wallet.get_payment(payment_hash)
        await payment.set_pending(False)
        ticket = await set_ticket_paid(payment_hash=payment_hash)

        return jsonify({"paid": True, "ticket_id": ticket.id}), HTTPStatus.OK

    return jsonify({"paid": False}), HTTPStatus.OK


@events_ext.route("/api/v1/tickets/<ticket_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_ticket_delete(ticket_id):
    ticket = await get_ticket(ticket_id)

    if not ticket:
        return jsonify({"message": "Ticket does not exist."}), HTTPStatus.NOT_FOUND

    if ticket.wallet != g.wallet.id:
        return jsonify({"message": "Not your ticket."}), HTTPStatus.FORBIDDEN

    await delete_ticket(ticket_id)
    return "", HTTPStatus.NO_CONTENT


# Event Tickets


@events_ext.route("/api/v1/eventtickets/<wallet_id>/<event_id>", methods=["GET"])
async def api_event_tickets(wallet_id, event_id):
    return (
        jsonify(
            [
                ticket._asdict()
                for ticket in await get_event_tickets(
                    wallet_id=wallet_id, event_id=event_id
                )
            ]
        ),
        HTTPStatus.OK,
    )


@events_ext.route("/api/v1/register/ticket/<ticket_id>", methods=["GET"])
async def api_event_register_ticket(ticket_id):
    ticket = await get_ticket(ticket_id)
    if not ticket:
        return jsonify({"message": "Ticket does not exist."}), HTTPStatus.FORBIDDEN

    if not ticket.paid:
        return jsonify({"message": "Ticket not paid for."}), HTTPStatus.FORBIDDEN

    if ticket.registered == True:
        return jsonify({"message": "Ticket already registered"}), HTTPStatus.FORBIDDEN

    return (
        jsonify([ticket._asdict() for ticket in await reg_ticket(ticket_id)]),
        HTTPStatus.OK,
    )
