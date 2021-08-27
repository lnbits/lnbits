from lnbits.helpers import url_for
from fastapi.param_functions import Depends
from lnbits.auth_bearer import AuthBearer
from pydantic import BaseModel
import trio
import json
import httpx
import hashlib
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs, ParseResult

from fastapi import Query

from http import HTTPStatus
from binascii import unhexlify
from typing import Dict, List, Optional, Union

from lnbits import bolt11, lnurl
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.utils.exchange_rates import currencies, fiat_amount_as_satoshis
from lnbits.requestvars import g

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


@core_app.get(
    "/api/v1/wallet",
    # dependencies=[Depends(AuthBearer())]
)
# @api_check_wallet_key("invoice")
async def api_wallet():
    return (
            {"id": g().wallet.id, "name": g().wallet.name, "balance": g().wallet.balance_msat},
        HTTPStatus.OK,
    )


@core_app.put("/api/v1/wallet/{new_name}")
@api_check_wallet_key("invoice")
async def api_update_wallet(new_name: str):
    await update_wallet(g().wallet.id, new_name)
    return (
            {
                "id": g().wallet.id,
                "name": g().wallet.name,
                "balance": g().wallet.balance_msat,
            },
        HTTPStatus.OK,
    )


@core_app.get("/api/v1/payments")
@api_check_wallet_key("invoice")
async def api_payments():
    return (
            await get_payments(wallet_id=g().wallet.id, pending=True, complete=True),
        HTTPStatus.OK,
    )

class CreateInvoiceData(BaseModel):
    amount:  int = Query(None, ge=1)
    memo:  str = None
    unit:  Optional[str] = None
    description_hash:  str = None
    lnurl_callback:  Optional[str] = None
    lnurl_balance_check:  Optional[str] = None
    extra:  Optional[dict] = None
    webhook:  Optional[str] = None

@api_check_wallet_key("invoice")
# async def api_payments_create_invoice(amount: List[str] = Query([type: str = Query(None)])):
async def api_payments_create_invoice(data: CreateInvoiceData):
    if "description_hash" in data:
        description_hash = unhexlify(data.description_hash)
        memo = ""
    else:
        description_hash = b""
        memo = data.memo

    if data.unit or "sat" == "sat":
        amount = data.amount
    else:
        price_in_sats = await fiat_amount_as_satoshis(data.amount, data.unit)
        amount = price_in_sats

    async with db.connect() as conn:
        try:
            payment_hash, payment_request = await create_invoice(
                wallet_id=g().wallet.id,
                amount=amount,
                memo=memo,
                description_hash=description_hash,
                extra=data.extra,
                webhook=data.webhook,
                conn=conn,
            )
        except InvoiceFailure as e:
            return {"message": str(e)}, 520
        except Exception as exc:
            raise exc

    invoice = bolt11.decode(payment_request)

    lnurl_response: Union[None, bool, str] = None
    if data.lnurl_callback:
        if "lnurl_balance_check" in g().data:
            save_balance_check(g().wallet.id, data.lnurl_balance_check)

        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(
                    data.lnurl_callback,
                    params={
                        "pr": payment_request,
                        "balanceNotify": url_for(
                            f"/withdraw/notify/{urlparse(data.lnurl_callback).netloc}",
                            external=True,
                            wal=g().wallet.id,
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
            {
                "payment_hash": invoice.payment_hash,
                "payment_request": payment_request,
                # maintain backwards compatibility with API clients:
                "checking_id": invoice.payment_hash,
                "lnurl_response": lnurl_response,
            },
        HTTPStatus.CREATED,
    )


@api_check_wallet_key("admin")
async def api_payments_pay_invoice(
    bolt11: str = Query(...), wallet: Optional[List[str]] = Query(None)
):
    try:
        payment_hash = await pay_invoice(
            wallet_id=wallet.id,
            payment_request=bolt11,
        )
    except ValueError as e:
        return {"message": str(e)}, HTTPStatus.BAD_REQUEST
    except PermissionError as e:
        return {"message": str(e)}, HTTPStatus.FORBIDDEN
    except PaymentFailure as e:
        return {"message": str(e)}, 520
    except Exception as exc:
        raise exc

    return (
            {
                "payment_hash": payment_hash,
                # maintain backwards compatibility with API clients:
                "checking_id": payment_hash,
            },
        HTTPStatus.CREATED,
    )


@core_app.post("/api/v1/payments")
async def api_payments_create(out: bool = True):
    if out is True:
        return await api_payments_pay_invoice()
    return await api_payments_create_invoice()

class CreateLNURLData(BaseModel):
    description_hash:  str
    callback:  str 
    amount:  int
    comment:  Optional[str] = None
    description:  Optional[str] = None

@core_app.post("/api/v1/payments/lnurl")
@api_check_wallet_key("admin")
async def api_payments_pay_lnurl(data: CreateLNURLData):
    domain = urlparse(data.callback).netloc

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                data.callback,
                params={"amount": data.amount, "comment": data.comment},
                timeout=40,
            )
            if r.is_error:
                raise httpx.ConnectError
        except (httpx.ConnectError, httpx.RequestError):
            return (
                {"message": f"Failed to connect to {domain}."},
                HTTPStatus.BAD_REQUEST,
            )

    params = json.loads(r.text)
    if params.get("status") == "ERROR":
        return ({"message": f"{domain} said: '{params.get('reason', '')}'"},
            HTTPStatus.BAD_REQUEST,
        )

    invoice = bolt11.decode(params["pr"])
    if invoice.amount_msat != data.amount:
        return (
                {
                    "message": f"{domain} returned an invalid invoice. Expected {g().data['amount']} msat, got {invoice.amount_msat}."
                },
            HTTPStatus.BAD_REQUEST,
        )
    if invoice.description_hash != g().data["description_hash"]:
        return (
                {
                    "message": f"{domain} returned an invalid invoice. Expected description_hash == {g().data['description_hash']}, got {invoice.description_hash}."
                },
            HTTPStatus.BAD_REQUEST,
        )

    extra = {}

    if params.get("successAction"):
        extra["success_action"] = params["successAction"]
    if data.comment:
        extra["comment"] = data.comment

    payment_hash = await pay_invoice(
        wallet_id=g().wallet.id,
        payment_request=params["pr"],
        description=data.description,
        extra=extra,
    )

    return (
            {
                "success_action": params.get("successAction"),
                "payment_hash": payment_hash,
                # maintain backwards compatibility with API clients:
                "checking_id": payment_hash,
            },
        HTTPStatus.CREATED,
    )


@core_app.get("/api/v1/payments/{payment_hash}")
@api_check_wallet_key("invoice")
async def api_payment(payment_hash):
    payment = await g().wallet.get_payment(payment_hash)

    if not payment:
        return {"message": "Payment does not exist."}, HTTPStatus.NOT_FOUND
    elif not payment.pending:
        return {"paid": True, "preimage": payment.preimage}, HTTPStatus.OK

    try:
        await payment.check_pending()
    except Exception:
        return {"paid": False}, HTTPStatus.OK

    return (
        {"paid": not payment.pending, "preimage": payment.preimage},
        HTTPStatus.OK,
    )


@core_app.get("/api/v1/payments/sse")
@api_check_wallet_key("invoice", accept_querystring=True)
async def api_payments_sse():
    this_wallet_id = g().wallet.id

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


@core_app.get("/api/v1/lnurlscan/{code}")
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
            return {"message": "invalid lnurl"}, HTTPStatus.BAD_REQUEST

    # params is what will be returned to the client
    params: Dict = {"domain": domain}

    if "tag=login" in url:
        params.update(kind="auth")
        params.update(callback=url)  # with k1 already in it

        lnurlauth_key = g().wallet.lnurlauth_key(domain)
        params.update(pubkey=lnurlauth_key.verifying_key.to_string("compressed").hex())
    else:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=5)
            if r.is_error:
                return (
                    {"domain": domain, "message": "failed to get parameters"},
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )

        try:
            data = json.loads(r.text)
        except json.decoder.JSONDecodeError:
            return (
                    {
                        "domain": domain,
                        "message": f"got invalid response '{r.text[:200]}'",
                    },
                HTTPStatus.SERVICE_UNAVAILABLE,
            )

        try:
            tag = data["tag"]
            if tag == "channelRequest":
                return (
                        {"domain": domain, "kind": "channel", "message": "unsupported"},
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
                    {
                        "domain": domain,
                        "message": f"lnurl JSON response invalid: {exc}",
                    },
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
    return params


@core_app.post("/api/v1/lnurlauth")
@api_check_wallet_key("admin")
async def api_perform_lnurlauth(callback: str):
    err = await perform_lnurlauth(callback)
    if err:
        return {"reason": err.reason}, HTTPStatus.SERVICE_UNAVAILABLE
    return "", HTTPStatus.OK


@core_app.route("/api/v1/currencies", methods=["GET"])
async def api_list_currencies_available():
    return list(currencies.keys())
