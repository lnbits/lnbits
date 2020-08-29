import hashlib
from flask import g, jsonify, request, url_for
from http import HTTPStatus
from lnurl import LnurlPayResponse, LnurlPayActionResponse
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl

from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.settings import FORCE_HTTPS

from lnbits.extensions.lnurlp import lnurlp_ext
from .crud import (
    create_pay_link,
    get_pay_link,
    get_pay_links,
    update_pay_link,
    increment_pay_link,
    delete_pay_link,
)


@lnurlp_ext.route("/api/v1/links", methods=["GET"])
@api_check_wallet_key("invoice")
def api_links():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    try:
        return (
            jsonify([{**link._asdict(), **{"lnurl": link.lnurl}} for link in get_pay_links(wallet_ids)]),
            HTTPStatus.OK,
        )
    except LnurlInvalidUrl:
        return (
            jsonify({"message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor."}),
            HTTPStatus.UPGRADE_REQUIRED,
        )


@lnurlp_ext.route("/api/v1/links/<link_id>", methods=["GET"])
@api_check_wallet_key("invoice")
def api_link_retrieve(link_id):
    link = get_pay_link(link_id)

    if not link:
        return jsonify({"message": "Pay link does not exist."}), HTTPStatus.NOT_FOUND

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your pay link."}), HTTPStatus.FORBIDDEN

    return jsonify({**link._asdict(), **{"lnurl": link.lnurl}}), HTTPStatus.OK


@lnurlp_ext.route("/api/v1/links", methods=["POST"])
@lnurlp_ext.route("/api/v1/links/<link_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "description": {"type": "string", "empty": False, "required": True},
        "amount": {"type": "integer", "min": 1, "required": True},
    }
)
def api_link_create_or_update(link_id=None):
    if link_id:
        link = get_pay_link(link_id)

        if not link:
            return jsonify({"message": "Pay link does not exist."}), HTTPStatus.NOT_FOUND

        if link.wallet != g.wallet.id:
            return jsonify({"message": "Not your pay link."}), HTTPStatus.FORBIDDEN

        link = update_pay_link(link_id, **g.data)
    else:
        link = create_pay_link(wallet_id=g.wallet.id, **g.data)

    return jsonify({**link._asdict(), **{"lnurl": link.lnurl}}), HTTPStatus.OK if link_id else HTTPStatus.CREATED


@lnurlp_ext.route("/api/v1/links/<link_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
def api_link_delete(link_id):
    link = get_pay_link(link_id)

    if not link:
        return jsonify({"message": "Pay link does not exist."}), HTTPStatus.NOT_FOUND

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your pay link."}), HTTPStatus.FORBIDDEN

    delete_pay_link(link_id)

    return "", HTTPStatus.NO_CONTENT


@lnurlp_ext.route("/api/v1/lnurl/<link_id>", methods=["GET"])
def api_lnurl_response(link_id):
    link = increment_pay_link(link_id, served_meta=1)
    if not link:
        return jsonify({"status": "ERROR", "reason": "LNURL-pay not found."}), HTTPStatus.OK

    scheme = "https" if FORCE_HTTPS else None
    url = url_for("lnurlp.api_lnurl_callback", link_id=link.id, _external=True, _scheme=scheme)

    resp = LnurlPayResponse(
        callback=url, min_sendable=link.amount * 1000, max_sendable=link.amount * 1000, metadata=link.lnurlpay_metadata,
    )

    return jsonify(resp.dict()), HTTPStatus.OK


@lnurlp_ext.route("/api/v1/lnurl/cb/<link_id>", methods=["GET"])
def api_lnurl_callback(link_id):
    link = increment_pay_link(link_id, served_pr=1)
    if not link:
        return jsonify({"status": "ERROR", "reason": "LNURL-pay not found."}), HTTPStatus.OK

    _, payment_request = create_invoice(
        wallet_id=link.wallet,
        amount=link.amount,
        memo=link.description,
        description_hash=hashlib.sha256(link.lnurlpay_metadata.encode("utf-8")).digest(),
    )
    resp = LnurlPayActionResponse(pr=payment_request, success_action=None, routes=[])

    return jsonify(resp.dict()), HTTPStatus.OK
