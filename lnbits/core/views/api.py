<<<<<<< HEAD
import trio  # type: ignore
import json
import traceback
from quart import g, jsonify, request, make_response
=======
import lnurl
from quart import g, jsonify, request
>>>>>>> da8fd9a... send/create buttons wip.
from http import HTTPStatus
from binascii import unhexlify
from urllib.parse import urlparse

from lnbits import bolt11
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from .. import core_app
from ..services import create_invoice, pay_invoice
from ..crud import delete_expired_invoices
from ..tasks import sse_listeners


@core_app.route("/api/v1/wallet", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_wallet():
    return (
        jsonify(
            {
                "id": g.wallet.id,
                "name": g.wallet.name,
                "balance": g.wallet.balance_msat,
            }
        ),
        HTTPStatus.OK,
    )


@core_app.route("/api/v1/payments", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_payments():
    if "check_pending" in request.args:
        delete_expired_invoices()

        for payment in g.wallet.get_payments(complete=False, pending=True, exclude_uncheckable=True):
            payment.check_pending()

    return jsonify(g.wallet.get_payments(pending=True)), HTTPStatus.OK


@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "amount": {"type": "integer", "min": 1, "required": True},
        "memo": {"type": "string", "empty": False, "required": True, "excludes": "description_hash"},
        "description_hash": {"type": "string", "empty": False, "required": True, "excludes": "memo"},
    }
)
async def api_payments_create_invoice():
    if "description_hash" in g.data:
        description_hash = unhexlify(g.data["description_hash"])
        memo = ""
    else:
        description_hash = b""
        memo = g.data["memo"]

    try:
        payment_hash, payment_request = create_invoice(
            wallet_id=g.wallet.id, amount=g.data["amount"], memo=memo, description_hash=description_hash
        )
    except Exception as e:
        g.db.rollback()
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    invoice = bolt11.decode(payment_request)
    return (
        jsonify(
            {
                "payment_hash": invoice.payment_hash,
                "payment_request": payment_request,
                # maintain backwards compatibility with API clients:
                "checking_id": invoice.payment_hash,
            }
        ),
        HTTPStatus.CREATED,
    )


@api_check_wallet_key("admin")
@api_validate_post_request(schema={"bolt11": {"type": "string", "empty": False, "required": True}})
async def api_payments_pay_invoice():
    try:
        payment_hash = pay_invoice(wallet_id=g.wallet.id, payment_request=g.data["bolt11"])
    except ValueError as e:
        return jsonify({"message": str(e)}), HTTPStatus.BAD_REQUEST
    except PermissionError as e:
        return jsonify({"message": str(e)}), HTTPStatus.FORBIDDEN
    except Exception as exc:
        traceback.print_exc(7)
        g.db.rollback()
        return jsonify({"message": str(exc)}), HTTPStatus.INTERNAL_SERVER_ERROR

    return (
        jsonify(
            {
                "payment_hash": payment_hash,
                # maintain backwards compatibility with API clients:
                "checking_id": payment_hash,
            }
        ),
        HTTPStatus.CREATED,
    )


@core_app.route("/api/v1/payments", methods=["POST"])
@api_validate_post_request(schema={"out": {"type": "boolean", "required": True}})
async def api_payments_create():
    if g.data["out"] is True:
        return await api_payments_pay_invoice()
    return await api_payments_create_invoice()


@core_app.route("/api/v1/payments/<payment_hash>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_payment(payment_hash):
    payment = g.wallet.get_payment(payment_hash)

    if not payment:
        return jsonify({"message": "Payment does not exist."}), HTTPStatus.NOT_FOUND
    elif not payment.pending:
        return jsonify({"paid": True}), HTTPStatus.OK

    try:
        payment.check_pending()
    except Exception:
        return jsonify({"paid": False}), HTTPStatus.OK

    return jsonify({"paid": not payment.pending}), HTTPStatus.OK


<<<<<<< HEAD
@core_app.route("/api/v1/payments/sse", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_payments_sse():
    g.db.close()
    this_wallet_id = g.wallet.id

    send_payment, receive_payment = trio.open_memory_channel(0)

    print("adding sse listener", send_payment)
    sse_listeners.append(send_payment)

    send_event, receive_event = trio.open_memory_channel(0)

    async def payment_received() -> None:
        async for payment in receive_payment:
            if payment.wallet_id == this_wallet_id:
                await send_event.send(("payment", payment))

    async def repeat_keepalive():
        await trio.sleep(1)
        while True:
            await send_event.send(("keepalive", ""))
            await trio.sleep(25)

    g.nursery.start_soon(payment_received)
    g.nursery.start_soon(repeat_keepalive)

    async def send_events():
        try:
            async for typ, data in receive_event:
                message = [f"event: {typ}".encode("utf-8")]

                if data:
                    jdata = json.dumps(dict(data._asdict(), pending=False))
                    message.append(f"data: {jdata}".encode("utf-8"))

                yield b"\n".join(message) + b"\r\n\r\n"
        except trio.Cancelled:
            return

    response = await make_response(
        send_events(),
        {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        },
    )
    response.timeout = None
    return response
=======
    return jsonify({"paid": False}), HTTPStatus.OK


@core_app.route("/api/v1/lnurlscan/<code>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_lnurlscan(code: str):
    try:
        url = lnurl.Lnurl(code)
    except ValueError:
        return jsonify({"error": "invalid lnurl"}), HTTPStatus.BAD_REQUEST

    domain = urlparse(url.url).netloc
    if url.is_login:
        return jsonify({"domain": domain, "kind": "auth", "error": "unsupported"})

    data: lnurl.LnurlResponseModel = lnurl.get(url.url)
    if not data.ok:
        return jsonify({"domain": domain, "error": "failed to get parameters"})

    if type(data) is lnurl.LnurlChannelResponse:
        return jsonify({"domain": domain, "kind": "channel", "error": "unsupported"})

    params = data.dict()
    if type(data) is lnurl.LnurlWithdrawResponse:
        params.update(kind="withdraw", fixed=data.min_withdrawable == data.max_withdrawable)

    if type(data) is lnurl.LnurlPayResponse:
        params.update(kind="pay", fixed=data.min_sendable == data.max_sendable)

    params.update(domain=domain)
    return jsonify(params)
>>>>>>> da8fd9a... send/create buttons wip.
