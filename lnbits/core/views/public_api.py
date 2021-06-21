import trio
import datetime
from http import HTTPStatus
from quart import jsonify

from lnbits import bolt11

from .. import core_app
from ..crud import get_standalone_payment
from ..tasks import api_invoice_listeners


@core_app.route("/public/v1/payment/<payment_hash>", methods=["GET"])
async def api_public_payment_longpolling(payment_hash):
    payment = await get_standalone_payment(payment_hash)

    if not payment:
        return jsonify({"message": "Payment does not exist."}), HTTPStatus.NOT_FOUND
    elif not payment.pending:
        return jsonify({"status": "paid"}), HTTPStatus.OK

    try:
        invoice = bolt11.decode(payment.bolt11)
        expiration = datetime.datetime.fromtimestamp(invoice.date + invoice.expiry)
        if expiration < datetime.datetime.now():
            return jsonify({"status": "expired"}), HTTPStatus.OK
    except:
        return jsonify({"message": "Invalid bolt11 invoice."}), HTTPStatus.BAD_REQUEST

    send_payment, receive_payment = trio.open_memory_channel(0)

    print("adding standalone invoice listener", payment_hash, send_payment)
    api_invoice_listeners.append(send_payment)

    async for payment in receive_payment:
        if payment.payment_hash == payment_hash:
            return jsonify({"status": "paid"}), HTTPStatus.OK
