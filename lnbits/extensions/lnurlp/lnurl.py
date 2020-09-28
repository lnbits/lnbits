import hashlib
from http import HTTPStatus
from quart import jsonify, url_for
from lnurl import LnurlPayResponse, LnurlPayActionResponse
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl

from lnbits.core.services import create_invoice

from lnbits.extensions.lnurlp import lnurlp_ext
from .crud import increment_pay_link, save_link_invoice


@lnurlp_ext.route("/api/v1/lnurl/<link_id>", methods=["GET"])
async def api_lnurl_response(link_id):
    link = increment_pay_link(link_id, served_meta=1)
    if not link:
        return jsonify({"status": "ERROR", "reason": "LNURL-pay not found."}), HTTPStatus.OK

    url = url_for("lnurlp.api_lnurl_callback", link_id=link.id, _external=True)

    resp = LnurlPayResponse(
        callback=url,
        min_sendable=link.amount * 1000,
        max_sendable=link.amount * 1000,
        metadata=link.lnurlpay_metadata,
    )

    return jsonify(resp.dict()), HTTPStatus.OK


@lnurlp_ext.route("/api/v1/lnurl/cb/<link_id>", methods=["GET"])
async def api_lnurl_callback(link_id):
    link = increment_pay_link(link_id, served_pr=1)
    if not link:
        return jsonify({"status": "ERROR", "reason": "LNURL-pay not found."}), HTTPStatus.OK

    _, payment_request = create_invoice(
        wallet_id=link.wallet,
        amount=link.amount,
        memo=link.description,
        description_hash=hashlib.sha256(link.lnurlpay_metadata.encode("utf-8")).digest(),
        extra={"tag": "lnurlp"},
    )

    save_link_invoice(link_id, payment_request)

    resp = LnurlPayActionResponse(pr=payment_request, success_action=None, routes=[])

    return jsonify(resp.dict()), HTTPStatus.OK
