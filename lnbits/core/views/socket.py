from flask import g, request
from flask_socketio import SocketIO  # type: ignore

from lnbits.settings import WALLET
from lnbits.core.crud import get_wallet_for_key
from ..services import create_invoice, pay_invoice


# Did not have success creating decorator out of this.
def socket_validate_request(key_type: str = "invoice", json = None):
    key = ""
    try:
        key = json["X-Api-Key"]
    except:
        try:
            key = request.headers["X-Api-Key"]
        except:
            try:
                key = request.args["X-Api-Key"]
            except:
                pass

    if not key:
        raise Exception('No key given')

    g.wallet = get_wallet_for_key(key, key_type)

    if not g.wallet:
        raise Exception('No matching wallet')


# TODO default memo was set somewhere?
def socket(app) -> SocketIO:

    socketio = SocketIO(app)

    @socketio.on("wait_invoice")
    def handle_wait_invoice(json):
        socket_validate_request("invoice", json)

        checking_id = json["checking_id"]
        try:
            payment = g.wallet.get_payment(checking_id)
        except:
            return {"error": "No such invoice."}
        # Trying to listen in on someone else's payment.
        if not payment:
            return {"error": "No such invoice."}
        try:
            paid = not WALLET.wait_invoice(checking_id=checking_id).pending
            if paid:
                payment.set_pending(False)
        except:
            paid = False
        return {"paid": paid}

    @socketio.on("get_invoice")
    def handle_get_invoice(json):
        socket_validate_request("invoice", json)

        checking_id = json["checking_id"]
        if not checking_id:
            return {"error": "No such invoice"}
        checking_id, payment_request = g.wallet.get_payment(checking_id=checking_id)

        return {"checking_id": checking_id, "payment_request": payment_request}

    @socketio.on("create_invoice")
    def handle_create_invoice(json):
        socket_validate_request("invoice", json)

        wallet_id = g.wallet.id
        memo = json["memo"] or "lnbits invoice"
        checking_id, payment_request = create_invoice(amount=json["amount"], wallet_id=wallet_id, memo=memo)
        return {"checking_id": checking_id, "payment_request": payment_request}


    return socketio

