from flask import g, jsonify, request
from http import HTTPStatus

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.settings import WALLET

from lnbits.extensions.lnticket import lnticket_ext
from .crud import create_ticket, update_ticket, get_ticket, get_tickets, delete_ticket, create_form, update_form, get_form, get_forms, delete_form


#########FORMS##########

@lnticket_ext.route("/api/v1/forms", methods=["GET"])
@api_check_wallet_key("invoice")
def api_forms():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return jsonify([form._asdict() for form in get_forms(wallet_ids)]), HTTPStatus.OK


@lnticket_ext.route("/api/v1/forms", methods=["POST"])
@lnticket_ext.route("/api/v1/forms/<form_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "wallet": {"type": "string", "empty": False, "required": True},
        "name": {"type": "string", "empty": False, "required": True},
        "description": {"type": "string", "min": 0, "required": True},
        "costpword": {"type": "integer", "min": 0, "required": True}
    }
)
def api_form_create(form_id=None):
    if form_id:
        form = get_form(form_id)
        print(g.data)

        if not form:
            return jsonify({"message": "Form does not exist."}), HTTPStatus.NOT_FOUND

        if form.wallet != g.wallet.id:
            return jsonify({"message": "Not your form."}), HTTPStatus.FORBIDDEN

        form = update_form(form_id, **g.data)
    else:
        form = create_form(**g.data)
    return jsonify(form._asdict()), HTTPStatus.CREATED


@lnticket_ext.route("/api/v1/forms/<form_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
def api_form_delete(form_id):
    form = get_form(form_id)

    if not form:
        return jsonify({"message": "Form does not exist."}), HTTPStatus.NOT_FOUND

    if form.wallet != g.wallet.id:
        return jsonify({"message": "Not your form."}), HTTPStatus.FORBIDDEN

    delete_form(form_id)

    return "", HTTPStatus.NO_CONTENT




#########tickets##########

@lnticket_ext.route("/api/v1/tickets", methods=["GET"])
@api_check_wallet_key("invoice")
def api_tickets():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return jsonify([form._asdict() for form in get_tickets(wallet_ids)]), HTTPStatus.OK


@lnticket_ext.route("/api/v1/tickets/<form_id>/<sats>", methods=["POST"])
@api_validate_post_request(
    schema={
        "form": {"type": "string", "empty": False, "required": True},
        "name": {"type": "string", "empty": False, "required": True},
        "email": {"type": "string", "empty": False, "required": True},
        "ltext": {"type": "string", "empty": False, "required": True},
        "sats": {"type": "integer", "min": 0, "required": True}
    })
def api_ticket_make_ticket(form_id, sats):

    event = get_form(form_id)

    if not event:
        return jsonify({"message": "LNTicket does not exist."}), HTTPStatus.NOT_FOUND
    try:
        checking_id, payment_request = create_invoice(
            wallet_id=event.wallet, amount=int(sats), memo=f"#lnticket {form_id}"
        )
    except Exception as e:
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    ticket = create_ticket(checking_id=checking_id, wallet=event.wallet, **g.data)

    if not ticket:
        return jsonify({"message": "LNTicket could not be fetched."}), HTTPStatus.NOT_FOUND

    return jsonify({"checking_id": checking_id, "payment_request": payment_request}), HTTPStatus.OK


@lnticket_ext.route("/api/v1/tickets/<checking_id>", methods=["GET"])
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



@lnticket_ext.route("/api/v1/tickets/<ticket_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
def api_ticket_delete(ticket_id):
    ticket = get_ticket(ticket_id)

    if not ticket:
        return jsonify({"message": "Paywall does not exist."}), HTTPStatus.NOT_FOUND

    if ticket.wallet != g.wallet.id:
        return jsonify({"message": "Not your ticket."}), HTTPStatus.FORBIDDEN

    delete_ticket(ticket_id)

    return "", HTTPStatus.NO_CONTENT
