import json
import secrets
from http import HTTPStatus
from urllib.parse import urlparse

from fastapi import HTTPException, Query, Request
from lnurl import encode as lnurl_encode
from lnurl.types import LnurlPayMetadata
from starlette.responses import HTMLResponse

from lnbits import bolt11
from lnbits.core.services import create_invoice
from lnbits.core.views.api import pay_invoice

from . import boltcards_ext
from .crud import (
    create_hit,
    get_card,
    get_card_by_external_id,
    get_card_by_otp,
    get_hit,
    get_hits_today,
    spend_hit,
    update_card_counter,
    update_card_otp,
)
from .nxp424 import decryptSUN, getSunMAC

###############LNURLWITHDRAW#################


# /boltcards/api/v1/scan?p=00000000000000000000000000000000&c=0000000000000000
@boltcards_ext.get("/api/v1/scan/{external_id}")
async def api_scan(p, c, request: Request, external_id: str = Query(None)):
    # some wallets send everything as lower case, no bueno
    p = p.upper()
    c = c.upper()
    card = None
    counter = b""
    card = await get_card_by_external_id(external_id)
    if not card:
        return {"status": "ERROR", "reason": "No card."}
    if not card.enable:
        return {"status": "ERROR", "reason": "Card is disabled."}
    try:
        card_uid, counter = decryptSUN(bytes.fromhex(p), bytes.fromhex(card.k1))
        if card.uid.upper() != card_uid.hex().upper():
            return {"status": "ERROR", "reason": "Card UID mis-match."}
        if c != getSunMAC(card_uid, counter, bytes.fromhex(card.k2)).hex().upper():
            return {"status": "ERROR", "reason": "CMAC does not check."}
    except:
        return {"status": "ERROR", "reason": "Error decrypting card."}

    ctr_int = int.from_bytes(counter, "little")

    if ctr_int <= card.counter:
        return {"status": "ERROR", "reason": "This link is already used."}

    await update_card_counter(ctr_int, card.id)

    # gathering some info for hit record
    assert request.client
    ip = request.client.host
    if "x-real-ip" in request.headers:
        ip = request.headers["x-real-ip"]
    elif "x-forwarded-for" in request.headers:
        ip = request.headers["x-forwarded-for"]

    agent = request.headers["user-agent"] if "user-agent" in request.headers else ""
    todays_hits = await get_hits_today(card.id)

    hits_amount = 0
    for hit in todays_hits:
        hits_amount = hits_amount + hit.amount
    if hits_amount > card.daily_limit:
        return {"status": "ERROR", "reason": "Max daily limit spent."}
    hit = await create_hit(card.id, ip, agent, card.counter, ctr_int)
    lnurlpay = lnurl_encode(request.url_for("boltcards.lnurlp_response", hit_id=hit.id))
    return {
        "tag": "withdrawRequest",
        "callback": request.url_for("boltcards.lnurl_callback", hitid=hit.id),
        "k1": hit.id,
        "minWithdrawable": 1 * 1000,
        "maxWithdrawable": card.tx_limit * 1000,
        "defaultDescription": f"Boltcard (refund address lnurl://{lnurlpay})",
    }


@boltcards_ext.get(
    "/api/v1/lnurl/cb/{hitid}",
    status_code=HTTPStatus.OK,
    name="boltcards.lnurl_callback",
)
async def lnurl_callback(
    pr: str = Query(None),
    k1: str = Query(None),
):
    if not k1:
        return {"status": "ERROR", "reason": "Missing K1 token"}

    hit = await get_hit(k1)

    if not hit:
        return {
            "status": "ERROR",
            "reason": "Record not found for this charge (bad k1)",
        }
    if hit.spent:
        return {"status": "ERROR", "reason": "Payment already claimed"}
    if not pr:
        return {"status": "ERROR", "reason": "Missing payment request"}

    try:
        invoice = bolt11.decode(pr)
    except:
        return {"status": "ERROR", "reason": "Failed to decode payment request"}

    card = await get_card(hit.card_id)
    assert card
    hit = await spend_hit(id=hit.id, amount=int(invoice.amount_msat / 1000))
    assert hit
    try:
        await pay_invoice(
            wallet_id=card.wallet,
            payment_request=pr,
            max_sat=card.tx_limit,
            extra={"tag": "boltcard", "hit": hit.id},
        )
        return {"status": "OK"}
    except Exception as exc:
        return {"status": "ERROR", "reason": f"Payment failed - {exc}"}


# /boltcards/api/v1/auth?a=00000000000000000000000000000000
@boltcards_ext.get("/api/v1/auth")
async def api_auth(a, request: Request):
    if a == "00000000000000000000000000000000":
        response = {"k0": "0" * 32, "k1": "1" * 32, "k2": "2" * 32}
        return response

    card = await get_card_by_otp(a)
    if not card:
        raise HTTPException(
            detail="Card does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    new_otp = secrets.token_hex(16)
    await update_card_otp(new_otp, card.id)

    lnurlw_base = (
        f"{urlparse(str(request.url)).netloc}/boltcards/api/v1/scan/{card.external_id}"
    )

    response = {
        "card_name": card.card_name,
        "id": str(1),
        "k0": card.k0,
        "k1": card.k1,
        "k2": card.k2,
        "k3": card.k1,
        "k4": card.k2,
        "lnurlw_base": "lnurlw://" + lnurlw_base,
        "protocol_name": "new_bolt_card_response",
        "protocol_version": str(1),
    }

    return response


###############LNURLPAY REFUNDS#################


@boltcards_ext.get(
    "/api/v1/lnurlp/{hit_id}",
    response_class=HTMLResponse,
    name="boltcards.lnurlp_response",
)
async def lnurlp_response(req: Request, hit_id: str = Query(None)):
    hit = await get_hit(hit_id)
    assert hit
    card = await get_card(hit.card_id)
    assert card
    if not hit:
        return {"status": "ERROR", "reason": "LNURL-pay record not found."}
    if not card.enable:
        return {"status": "ERROR", "reason": "Card is disabled."}
    payResponse = {
        "tag": "payRequest",
        "callback": req.url_for("boltcards.lnurlp_callback", hit_id=hit_id),
        "metadata": LnurlPayMetadata(json.dumps([["text/plain", "Refund"]])),
        "minSendable": 1 * 1000,
        "maxSendable": card.tx_limit * 1000,
    }
    return json.dumps(payResponse)


@boltcards_ext.get(
    "/api/v1/lnurlp/cb/{hit_id}",
    response_class=HTMLResponse,
    name="boltcards.lnurlp_callback",
)
async def lnurlp_callback(hit_id: str = Query(None), amount: str = Query(None)):
    hit = await get_hit(hit_id)
    assert hit
    card = await get_card(hit.card_id)
    assert card
    if not hit:
        return {"status": "ERROR", "reason": "LNURL-pay record not found."}

    _, payment_request = await create_invoice(
        wallet_id=card.wallet,
        amount=int(int(amount) / 1000),
        memo=f"Refund {hit_id}",
        unhashed_description=LnurlPayMetadata(
            json.dumps([["text/plain", "Refund"]])
        ).encode(),
        extra={"refund": hit_id},
    )

    payResponse = {"pr": payment_request, "routes": []}

    return json.dumps(payResponse)
