import hashlib
from quart import jsonify, url_for, request
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore
from urllib.parse import urlparse
import httpx, json

from lnbits.core.services import create_invoice

from . import lnaddress_ext
from .crud import get_address_by_username, get_address, get_domain

async def lnurl_response(username: str, domain: str):
    address = await get_address_by_username(username, domain)

    if not address:
        return jsonify({"status": "ERROR", "reason": "Address not found."})

    ## CHECK IF USER IS STILL VALID/PAYING
    # now =
    # if


    resp = LnurlPayResponse(
        callback=url_for("lnaddress.lnurl_callback", address_id=address.id, _external=True),
        min_sendable=1000,
        max_sendable=1000000000,
        metadata=await address.lnurlpay_metadata(),
    )

    return jsonify(resp.dict())

@lnaddress_ext.route("/lnurl/cb/<address_id>", methods=["GET"])
async def lnurl_callback(address_id):
    address = await get_address(address_id)

    if not address:
        return jsonify({"status": "ERROR", "reason": "Couldn't find username."})

    amount_received = int(request.args.get("amount") or 0)
    min = 1000
    max = 1000000000

    if amount_received < min:
        return jsonify(
            LnurlErrorResponse(
                reason=f"Amount {amount_received} is smaller than minimum."
            ).dict()
        )
    elif amount_received > max:
        return jsonify(
            LnurlErrorResponse(
                reason=f"Amount {amount_received} is greater than maximum."
            ).dict()
        )

    domain = await get_domain(address.domain)

    base_url = address.wallet_endpoint[:-1] if address.wallet_endpoint.endswith('/') else address.wallet_endpoint

    async with httpx.AsyncClient() as client:
        try:
            call = await client.post(
                base_url + "/api/v1/payments",
                headers={"X-Api-Key": address.wallet_key, "Content-Type": "application/json"},
                json={
                    "out": False,
                    "amount": int(amount_received / 1000),
                    "description_hash": hashlib.sha256((await address.lnurlpay_metadata()).encode("utf-8")).hexdigest(),
<<<<<<< HEAD
                    "extra": {"tag": "@" + address.username},
=======
                    "extra": {"tag": "@" + username},
>>>>>>> 661cf29cbf28a9a68bd5c266064579b9c7ec6d08
                },
                timeout=40,
            )

            r = call.json()
        except AssertionError as e:
            print("ERROR", e)
            return jsonify(LnurlErrorResponse(reason="ERROR"))

    print("R", r)

    resp = LnurlPayActionResponse(
        pr=r["payment_request"],
        routes=[],
    )
    print("RESP", resp)
    return jsonify(resp.dict())
