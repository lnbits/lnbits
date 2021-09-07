import hashlib
from quart import jsonify, url_for, request
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore

from lnbits.core.services import create_invoice

from . import lnaddress_ext
from .crud import get_address_by_username

async def lnurl_response(username: str, domain: str):
    address = await get_address_by_username(username, domain)

    if not address:
        return jsonify({"status": "ERROR", "reason": "Address not found."})

    ## CHECK IF USER IS STILL VALID/PAYING
    # now =
    # if


    resp = LnurlPayResponse(
        callback=url_for("lnaddress.lnurl_callback", username=address.username, _external=True),
        min_sendable=1000,
        max_sendable=1000000000,
        metadata="[[\"text/plain\", \"Tips powered by LNbits\"]]",
    )

    return jsonify(resp.dict())

@lnaddress_ext.route("/lnurl/cb/<username>", methods=["GET"])
async def lnurl_callback(item_id):
    print("ping")
    return
