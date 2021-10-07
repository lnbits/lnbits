import re
from quart import g, jsonify, request, abort
from http import HTTPStatus

from lnbits.core.crud import get_user, get_wallet, get_standalone_payment
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import lnticket_ext
from .crud import (
    create_ticket,
    set_ticket_paid,
    get_ticket,
    get_tickets,
    delete_ticket,
    create_form,
    update_form,
    get_form,
    get_forms,
    delete_form,
)


# FORMS


@lnticket_ext.route("/api/v1/forms", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_forms():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        jsonify([form._asdict() for form in await get_forms(wallet_ids)]),
        HTTPStatus.OK,
    )


@lnticket_ext.route("/api/v1/forms", methods=["POST"])
@lnticket_ext.route("/api/v1/forms/<form_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "wallet": {"type": "string", "empty": False, "required": True},
        "name": {"type": "string", "empty": False, "required": True},
        "webhook": {"type": "string", "required": False},
        "description": {"type": "string", "min": 0, "required": True},
        "amount": {"type": "integer", "min": 0, "required": True},
        "flatrate": {"type": "integer", "required": True},
    }
)
async def api_form_create(form_id=None):
    if form_id:
        form = await get_form(form_id)

        if not form:
            return jsonify({"message": "Form does not exist."}), HTTPStatus.NOT_FOUND

        if form.wallet != g.wallet.id:
            return jsonify({"message": "Not your form."}), HTTPStatus.FORBIDDEN

        form = await update_form(form_id, **g.data)
    else:
        form = await create_form(**g.data)
    return jsonify(form._asdict()), HTTPStatus.CREATED


@lnticket_ext.route("/api/v1/forms/<form_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_form_delete(form_id):
    form = await get_form(form_id)

    if not form:
        return jsonify({"message": "Form does not exist."}), HTTPStatus.NOT_FOUND

    if form.wallet != g.wallet.id:
        return jsonify({"message": "Not your form."}), HTTPStatus.FORBIDDEN

    await delete_form(form_id)

    return "", HTTPStatus.NO_CONTENT


#########tickets##########


@lnticket_ext.route("/api/v1/tickets", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_tickets():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        jsonify([form._asdict() for form in await get_tickets(wallet_ids)]),
        HTTPStatus.OK,
    )


@lnticket_ext.route("/api/v1/tickets/<form_id>", methods=["POST"])
@api_validate_post_request(
    schema={
        "form": {"type": "string", "empty": False, "required": True},
        "name": {"type": "string", "empty": False, "required": True},
        "email": {"type": "string", "empty": True, "required": True},
        "ltext": {"type": "string", "empty": False, "required": True},
        "sats": {"type": "integer", "min": 0, "required": True},
    }
)
async def api_ticket_make_ticket(form_id):
    form = await get_form(form_id)
    if not form:
        return jsonify({"message": "LNTicket does not exist."}), HTTPStatus.NOT_FOUND

    nwords = len(re.split(r"\s+", g.data["ltext"]))
    sats = g.data["sats"]

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=form.wallet,
            amount=sats,
            memo=f"ticket with {nwords} words on {form_id}",
            extra={"tag": "lnticket"},
        )
    except Exception as e:
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    ticket = await create_ticket(
        payment_hash=payment_hash, wallet=form.wallet, **g.data
    )

    if not ticket:
        return (
            jsonify({"message": "LNTicket could not be fetched."}),
            HTTPStatus.NOT_FOUND,
        )

    return (
        jsonify({"payment_hash": payment_hash, "payment_request": payment_request}),
        HTTPStatus.OK,
    )


@lnticket_ext.route("/api/v1/tickets/<payment_hash>", methods=["GET"])
async def api_ticket_send_ticket(payment_hash):
    ticket = await get_ticket(payment_hash) or abort(
        HTTPStatus.NOT_FOUND, "ticket does not exist."
    )
    payment = await get_standalone_payment(payment_hash) or abort(
        HTTPStatus.NOT_FOUND, "ticket payment does not exist."
    )
    if payment.pending == 1:
        await check_invoice_status(payment.wallet_id, payment_hash)
        payment = await get_standalone_payment(payment_hash) or abort(
            HTTPStatus.NOT_FOUND, "ticket payment does not exist."
        )
        if payment.pending == 1:
            return jsonify({"paid": False}), HTTPStatus.OK
    ticket = await set_ticket_paid(payment_hash=payment_hash)
    return jsonify({"paid": True}), HTTPStatus.OK


@lnticket_ext.route("/api/v1/tickets/<ticket_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_ticket_delete(ticket_id):
    ticket = await get_ticket(ticket_id)

    if not ticket:
        return jsonify({"message": "Paywall does not exist."}), HTTPStatus.NOT_FOUND

    if ticket.wallet != g.wallet.id:
        return jsonify({"message": "Not your ticket."}), HTTPStatus.FORBIDDEN

    await delete_ticket(ticket_id)

    return "", HTTPStatus.NO_CONTENT
