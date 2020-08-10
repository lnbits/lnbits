from flask import g, jsonify, request
from http import HTTPStatus

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.settings import WALLET

from lnbits.extensions.events import events_ext
from .crud import create_ticket, update_ticket, get_ticket, get_tickets, delete_ticket, create_event, update_event, get_event, get_events, delete_event, get_event_tickets, reg_ticket


#########Events##########


@events_ext.route("/api/v1/events", methods=["GET"])
@api_check_wallet_key("invoice")
def api_events():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return jsonify([event._asdict() for event in get_events(wallet_ids)]), HTTPStatus.OK


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
        "price_per_ticket": {"type": "integer", "min": 0, "required": True}
    }
)
def api_event_create(event_id=None):
    if event_id:
        event = get_event(event_id)
        print(g.data)

        if not event:
            return jsonify({"message": "Form does not exist."}), HTTPStatus.NOT_FOUND

        if event.wallet != g.wallet.id:
            return jsonify({"message": "Not your event."}), HTTPStatus.FORBIDDEN

        event = update_event(event_id, **g.data)
    else:
        event = create_event(**g.data)
        print(event)
    return jsonify(event._asdict()), HTTPStatus.CREATED


@events_ext.route("/api/v1/events/<event_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
def api_form_delete(event_id):
    event = get_event(event_id)

    if not event:
        return jsonify({"message": "Event does not exist."}), HTTPStatus.NOT_FOUND

    if event.wallet != g.wallet.id:
        return jsonify({"message": "Not your event."}), HTTPStatus.FORBIDDEN

    delete_event(event_id)

    return "", HTTPStatus.NO_CONTENT


#########Tickets##########

@events_ext.route("/api/v1/tickets", methods=["GET"])
@api_check_wallet_key("invoice")
def api_tickets():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return jsonify([ticket._asdict() for ticket in get_tickets(wallet_ids)]), HTTPStatus.OK


@events_ext.route("/api/v1/tickets/<event_id>/<sats>", methods=["POST"])
@api_validate_post_request(
    schema={
        "name": {"type": "string", "empty": False, "required": True},
        "email": {"type": "string", "empty": False, "required": True}
    })
def api_ticket_make_ticket(event_id, sats):

    event = get_event(event_id)

    if not event:
        return jsonify({"message": "LNTicket does not exist."}), HTTPStatus.NOT_FOUND
    try:
        checking_id, payment_request = create_invoice(
            wallet_id=event.wallet, amount=int(sats), memo=f"#lnticket {event_id}"
        )
    except Exception as e:
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    ticket = create_ticket(checking_id=checking_id, wallet=event.wallet, event=event_id, **g.data)

    if not ticket:
        return jsonify({"message": "LNTicket could not be fetched."}), HTTPStatus.NOT_FOUND

    return jsonify({"checking_id": checking_id, "payment_request": payment_request}), HTTPStatus.OK


@events_ext.route("/api/v1/tickets/<checking_id>", methods=["GET"])
def api_ticket_send_ticket(checking_id):
    theticket = get_ticket(checking_id)
    try:
        is_paid = not WALLET.get_invoice_status(checking_id).pending
    except Exception:
        return jsonify({"message": "Not paid."}), HTTPStatus.NOT_FOUND

    if is_paid:
        wallet = get_wallet(theticket.wallet)
        payment = wallet.get_payment(checking_id)
        payment.set_pending(False)
        ticket = update_ticket(paid=True, checking_id=checking_id)

        return jsonify({"paid": True, "ticket_id": ticket.id}), HTTPStatus.OK

    return jsonify({"paid": False}), HTTPStatus.OK


@events_ext.route("/api/v1/tickets/<ticket_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
def api_ticket_delete(ticket_id):
    ticket = get_ticket(ticket_id)

    if not ticket:
        return jsonify({"message": "Ticket does not exist."}), HTTPStatus.NOT_FOUND

    if ticket.wallet != g.wallet.id:
        return jsonify({"message": "Not your ticket."}), HTTPStatus.FORBIDDEN

    delete_ticket(ticket_id)

    return "", HTTPStatus.NO_CONTENT


#########EventTickets##########

@events_ext.route("/api/v1/eventtickets/<wallet_id>/<event_id>", methods=["GET"])
def api_event_tickets(wallet_id, event_id):

    return jsonify([ticket._asdict() for ticket in get_event_tickets(wallet_id=wallet_id, event_id=event_id)]), HTTPStatus.OK

@events_ext.route("/api/v1/register/ticket/<ticket_id>", methods=["GET"])
def api_event_register_ticket(ticket_id):
    
    ticket = get_ticket(ticket_id)

    if not ticket:
        return jsonify({"message": "Ticket does not exist."}), HTTPStatus.FORBIDDEN

    if ticket.registered == True:
        return jsonify({"message": "Ticket already registered"}), HTTPStatus.FORBIDDEN


    return jsonify([ticket._asdict() for ticket in reg_ticket(ticket_id)]), HTTPStatus.OK

