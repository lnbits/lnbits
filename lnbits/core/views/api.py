import trio
import json
import httpx
import hashlib
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs, ParseResult
from quart import g, current_app, jsonify, make_response, url_for
from http import HTTPStatus
from binascii import unhexlify
from typing import Dict, Union

from lnbits import bolt11, lnurl
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.utils.exchange_rates import currencies, fiat_amount_as_satoshis

from .. import core_app, db
from ..crud import get_payments, save_balance_check, update_wallet
from ..services import (
    PaymentFailure,
    InvoiceFailure,
    create_invoice,
    pay_invoice,
    perform_lnurlauth,
)
from ..tasks import api_invoice_listeners


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

@core_app.route("/api/v1/wallet/<new_name>", methods=["PUT"])
@api_check_wallet_key("invoice")
async def api_update_wallet(new_name):
    await update_wallet(g.wallet.id, new_name)
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
    return jsonify(await get_payments(wallet_id=g.wallet.id, pending=True, complete=True))


@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "amount": {"type": "number", "min": 0.001, "required": True},
        "memo": {
            "type": "string",
            "empty": False,
            "required": True,
            "excludes": "description_hash",
        },
        "unit": {"type": "string", "empty": False, "required": False},
        "description_hash": {
            "type": "string",
            "empty": False,
            "required": True,
            "excludes": "memo",
        },
        "lnurl_callback": {"type": "string", "nullable": True, "required": False},
        "lnurl_balance_check": {"type": "string", "required": False},
        "extra": {"type": "dict", "nullable": True, "required": False},
        "webhook": {"type": "string", "empty": False, "required": False},
    }
)
async def api_payments_create_invoice():
    if "description_hash" in g.data:
        description_hash = unhexlify(g.data["description_hash"])
        memo = ""
    else:
        description_hash = b""
        memo = g.data["memo"]

    if g.data.get("unit") or "sat" == "sat":
        amount = g.data["amount"]
    else:
        price_in_sats = await fiat_amount_as_satoshis(g.data["amount"], g.data["unit"])
        amount = price_in_sats

    async with db.connect() as conn:
        try:
            payment_hash, payment_request = await create_invoice(
                wallet_id=g.wallet.id,
                amount=amount,
                memo=memo,
                description_hash=description_hash,
                extra=g.data.get("extra"),
                webhook=g.data.get("webhook"),
                conn=conn,
            )
        except InvoiceFailure as e:
            return jsonify({"message": str(e)}), 520
        except Exception as exc:
            raise exc

    invoice = bolt11.decode(payment_request)

    lnurl_response: Union[None, bool, str] = None
    if g.data.get("lnurl_callback"):
        if "lnurl_balance_check" in g.data:
            save_balance_check(g.wallet.id, g.data["lnurl_balance_check"])

        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(
                    g.data["lnurl_callback"],
                    params={
                        "pr": payment_request,
                        "balanceNotify": url_for(
                            "core.lnurl_balance_notify",
                            service=urlparse(g.data["lnurl_callback"]).netloc,
                            wal=g.wallet.id,
                            _external=True,
                        ),
                    },
                    timeout=10,
                )
                if r.is_error:
                    lnurl_response = r.text
                else:
                    resp = json.loads(r.text)
                    if resp["status"] != "OK":
                        lnurl_response = resp["reason"]
                    else:
                        lnurl_response = True
            except (httpx.ConnectError, httpx.RequestError):
                lnurl_response = False

    return (
        jsonify(
            {
                "payment_hash": invoice.payment_hash,
                "payment_request": payment_request,
                # maintain backwards compatibility with API clients:
                "checking_id": invoice.payment_hash,
                "lnurl_response": lnurl_response,
            }
        ),
        HTTPStatus.CREATED,
    )


@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={"bolt11": {"type": "string", "empty": False, "required": True}}
)
async def api_payments_pay_invoice():
    try:
        payment_hash = await pay_invoice(
            wallet_id=g.wallet.id,
            payment_request=g.data["bolt11"],
        )
    except ValueError as e:
        return jsonify({"message": str(e)}), HTTPStatus.BAD_REQUEST
    except PermissionError as e:
        return jsonify({"message": str(e)}), HTTPStatus.FORBIDDEN
    except PaymentFailure as e:
        return jsonify({"message": str(e)}), 520
    except Exception as exc:
        raise exc

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


@core_app.route("/api/v1/payments/lnurl", methods=["POST"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "description_hash": {"type": "string", "empty": False, "required": True},
        "callback": {"type": "string", "empty": False, "required": True},
        "amount": {"type": "number", "empty": False, "required": True},
        "comment": {
            "type": "string",
            "nullable": True,
            "empty": True,
            "required": False,
        },
        "description": {
            "type": "string",
            "nullable": True,
            "empty": True,
            "required": False,
        },
    }
)
async def api_payments_pay_lnurl():
    domain = urlparse(g.data["callback"]).netloc

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                g.data["callback"],
                params={"amount": g.data["amount"], "comment": g.data["comment"]},
                timeout=40,
            )
            if r.is_error:
                raise httpx.ConnectError
        except (httpx.ConnectError, httpx.RequestError):
            return (
                jsonify({"message": f"Failed to connect to {domain}."}),
                HTTPStatus.BAD_REQUEST,
            )

    params = json.loads(r.text)
    if params.get("status") == "ERROR":
        return (
            jsonify({"message": f"{domain} said: '{params.get('reason', '')}'"}),
            HTTPStatus.BAD_REQUEST,
        )

    invoice = bolt11.decode(params["pr"])
    if invoice.amount_msat != g.data["amount"]:
        return (
            jsonify(
                {
                    "message": f"{domain} returned an invalid invoice. Expected {g.data['amount']} msat, got {invoice.amount_msat}."
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )
    if invoice.description_hash != g.data["description_hash"]:
        return (
            jsonify(
                {
                    "message": f"{domain} returned an invalid invoice. Expected description_hash == {g.data['description_hash']}, got {invoice.description_hash}."
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )

    extra = {}

    if params.get("successAction"):
        extra["success_action"] = params["successAction"]
    if g.data["comment"]:
        extra["comment"] = g.data["comment"]

    payment_hash = await pay_invoice(
        wallet_id=g.wallet.id,
        payment_request=params["pr"],
        description=g.data.get("description", ""),
        extra=extra,
    )

    return (
        jsonify(
            {
                "success_action": params.get("successAction"),
                "payment_hash": payment_hash,
                # maintain backwards compatibility with API clients:
                "checking_id": payment_hash,
            }
        ),
        HTTPStatus.CREATED,
    )


@core_app.route("/api/v1/payments/<payment_hash>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_payment(payment_hash):
    payment = await g.wallet.get_payment(payment_hash)

    if not payment:
        return jsonify({"message": "Payment does not exist."}), HTTPStatus.NOT_FOUND
    elif not payment.pending:
        return jsonify({"paid": True, "preimage": payment.preimage}), HTTPStatus.OK

    try:
        await payment.check_pending()
    except Exception:
        return jsonify({"paid": False}), HTTPStatus.OK

    return (
        jsonify({"paid": not payment.pending, "preimage": payment.preimage}),
        HTTPStatus.OK,
    )


@core_app.route("/api/v1/payments/sse", methods=["GET"])
@api_check_wallet_key("invoice", accept_querystring=True)
async def api_payments_sse():
    this_wallet_id = g.wallet.id

    send_payment, receive_payment = trio.open_memory_channel(0)

    print("adding sse listener", send_payment)
    api_invoice_listeners.append(send_payment)

    send_event, event_to_send = trio.open_memory_channel(0)

    async def payment_received() -> None:
        async for payment in receive_payment:
            if payment.wallet_id == this_wallet_id:
                await send_event.send(("payment-received", payment))

    async def repeat_keepalive():
        await trio.sleep(1)
        while True:
            await send_event.send(("keepalive", ""))
            await trio.sleep(25)

    current_app.nursery.start_soon(payment_received)
    current_app.nursery.start_soon(repeat_keepalive)

    async def send_events():
        try:
            async for typ, data in event_to_send:
                message = [f"event: {typ}".encode("utf-8")]

                if data:
                    jdata = json.dumps(dict(data._asdict(), pending=False), default=str)
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


@core_app.route("/api/v1/lnurlscan/<code>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_lnurlscan(code: str):
    try:
        url = lnurl.decode(code)
        domain = urlparse(url).netloc
    except:
        # parse internet identifier (user@domain.com)
        name_domain = code.split("@")
        if len(name_domain) == 2 and len(name_domain[1].split(".")) == 2:
            name, domain = name_domain
            url = (
                ("http://" if domain.endswith(".onion") else "https://")
                + domain
                + "/.well-known/lnurlp/"
                + name
            )
            # will proceed with these values
        else:
            return jsonify({"message": "invalid lnurl"}), HTTPStatus.BAD_REQUEST

    # params is what will be returned to the client
    params: Dict = {"domain": domain}

    if "tag=login" in url:
        params.update(kind="auth")
        params.update(callback=url)  # with k1 already in it

        lnurlauth_key = g.wallet.lnurlauth_key(domain)
        params.update(pubkey=lnurlauth_key.verifying_key.to_string("compressed").hex())
    else:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=5)
            if r.is_error:
                return (
                    jsonify({"domain": domain, "message": "failed to get parameters"}),
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )

        try:
            data = json.loads(r.text)
        except json.decoder.JSONDecodeError:
            return (
                jsonify(
                    {
                        "domain": domain,
                        "message": f"got invalid response '{r.text[:200]}'",
                    }
                ),
                HTTPStatus.SERVICE_UNAVAILABLE,
            )

        try:
            tag = data["tag"]
            if tag == "channelRequest":
                return (
                    jsonify(
                        {"domain": domain, "kind": "channel", "message": "unsupported"}
                    ),
                    HTTPStatus.BAD_REQUEST,
                )

            params.update(**data)

            if tag == "withdrawRequest":
                params.update(kind="withdraw")
                params.update(fixed=data["minWithdrawable"] == data["maxWithdrawable"])

                # callback with k1 already in it
                parsed_callback: ParseResult = urlparse(data["callback"])
                qs: Dict = parse_qs(parsed_callback.query)
                qs["k1"] = data["k1"]

                # balanceCheck/balanceNotify
                if "balanceCheck" in data:
                    params.update(balanceCheck=data["balanceCheck"])

                # format callback url and send to client
                parsed_callback = parsed_callback._replace(
                    query=urlencode(qs, doseq=True)
                )
                params.update(callback=urlunparse(parsed_callback))

            if tag == "payRequest":
                params.update(kind="pay")
                params.update(fixed=data["minSendable"] == data["maxSendable"])

                params.update(
                    description_hash=hashlib.sha256(
                        data["metadata"].encode("utf-8")
                    ).hexdigest()
                )
                metadata = json.loads(data["metadata"])
                for [k, v] in metadata:
                    if k == "text/plain":
                        params.update(description=v)
                    if k == "image/jpeg;base64" or k == "image/png;base64":
                        data_uri = "data:" + k + "," + v
                        params.update(image=data_uri)
                    if k == "text/email" or k == "text/identifier":
                        params.update(targetUser=v)

                params.update(commentAllowed=data.get("commentAllowed", 0))
        except KeyError as exc:
            return (
                jsonify(
                    {
                        "domain": domain,
                        "message": f"lnurl JSON response invalid: {exc}",
                    }
                ),
                HTTPStatus.SERVICE_UNAVAILABLE,
            )

    return jsonify(params)


@core_app.route("/api/v1/lnurlauth", methods=["POST"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "callback": {"type": "string", "required": True},
    }
)
async def api_perform_lnurlauth():
    err = await perform_lnurlauth(g.data["callback"])
    if err:
        return jsonify({"reason": err.reason}), HTTPStatus.SERVICE_UNAVAILABLE
    return "", HTTPStatus.OK


@core_app.route("/api/v1/currencies", methods=["GET"])
async def api_list_currencies_available():
    return jsonify(list(currencies.keys()))
