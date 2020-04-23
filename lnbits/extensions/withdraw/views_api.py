from datetime import datetime
from flask import g, jsonify, request
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import pay_invoice
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.helpers import urlsafe_short_hash, Status

from lnbits.extensions.withdraw import withdraw_ext
from .crud import (
    create_withdraw_link,
    get_withdraw_link,
    get_withdraw_link_by_hash,
    get_withdraw_links,
    update_withdraw_link,
    delete_withdraw_link,
)


@withdraw_ext.route("/api/v1/links", methods=["GET"])
@api_check_wallet_key("invoice")
def api_links():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    try:
        return (
            jsonify([{**link._asdict(), **{"lnurl": link.lnurl}} for link in get_withdraw_links(wallet_ids)]),
            Status.OK,
        )
    except LnurlInvalidUrl:
        return (
            jsonify({"message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor."}),
            Status.UPGRADE_REQUIRED,
        )


@withdraw_ext.route("/api/v1/links/<link_id>", methods=["GET"])
@api_check_wallet_key("invoice")
def api_link_retrieve(link_id):
    link = get_withdraw_link(link_id)

    if not link:
        return jsonify({"message": "Withdraw link does not exist."}), Status.NOT_FOUND

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your withdraw link."}), Status.FORBIDDEN

    return jsonify({**link._asdict(), **{"lnurl": link.lnurl}}), Status.OK


@withdraw_ext.route("/api/v1/links", methods=["POST"])
@withdraw_ext.route("/api/v1/links/<link_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "title": {"type": "string", "empty": False, "required": True},
        "min_withdrawable": {"type": "integer", "min": 1, "required": True},
        "max_withdrawable": {"type": "integer", "min": 1, "required": True},
        "uses": {"type": "integer", "min": 1, "required": True},
        "wait_time": {"type": "integer", "min": 1, "required": True},
        "is_unique": {"type": "boolean", "required": True},
    }
)
def api_link_create_or_update(link_id=None):
    if g.data["max_withdrawable"] < g.data["min_withdrawable"]:
        return jsonify({"message": "`max_withdrawable` needs to be at least `min_withdrawable`."}), Status.BAD_REQUEST

    if (g.data["max_withdrawable"] * g.data["uses"] * 1000) > g.wallet.balance_msat:
        return jsonify({"message": "Insufficient balance."}), Status.FORBIDDEN

    if link_id:
        link = get_withdraw_link(link_id)

        if not link:
            return jsonify({"message": "Withdraw link does not exist."}), Status.NOT_FOUND

        if link.wallet != g.wallet.id:
            return jsonify({"message": "Not your withdraw link."}), Status.FORBIDDEN

        link = update_withdraw_link(link_id, **g.data)
    else:
        link = create_withdraw_link(wallet_id=g.wallet.id, **g.data)

    return jsonify({**link._asdict(), **{"lnurl": link.lnurl}}), Status.OK if link_id else Status.CREATED


@withdraw_ext.route("/api/v1/links/<link_id>", methods=["DELETE"])
@api_check_wallet_key("admin")
def api_link_delete(link_id):
    link = get_withdraw_link(link_id)

    if not link:
        return jsonify({"message": "Withdraw link does not exist."}), Status.NOT_FOUND

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your withdraw link."}), Status.FORBIDDEN

    delete_withdraw_link(link_id)

    return "", Status.NO_CONTENT


@withdraw_ext.route("/api/v1/lnurl/<unique_hash>", methods=["GET"])
def api_lnurl_response(unique_hash):
    link = get_withdraw_link_by_hash(unique_hash)

    if not link:
        return jsonify({"status": "ERROR", "reason": "LNURL-withdraw not found."}), Status.OK

    link = update_withdraw_link(link.id, k1=urlsafe_short_hash())

    return jsonify(link.lnurl_response.dict()), Status.OK


@withdraw_ext.route("/api/v1/lnurl/cb/<unique_hash>", methods=["GET"])
def api_lnurl_callback(unique_hash):
    link = get_withdraw_link_by_hash(unique_hash)
    k1 = request.args.get("k1", type=str)
    payment_request = request.args.get("pr", type=str)
    now = int(datetime.now().timestamp())

    if not link:
        return jsonify({"status": "ERROR", "reason": "LNURL-withdraw not found."}), Status.OK

    if link.is_spent:
        return jsonify({"status": "ERROR", "reason": "Withdraw is spent."}), Status.OK

    if link.k1 != k1:
        return jsonify({"status": "ERROR", "reason": "Bad request."}), Status.OK

    if now < link.open_time:
        return jsonify({"status": "ERROR", "reason": f"Wait {link.open_time - now} seconds."}), Status.OK

    try:
        pay_invoice(wallet=get_wallet(link.wallet), bolt11=payment_request, max_sat=link.max_withdrawable)

        changes = {
            "used": link.used + 1,
            "open_time": link.wait_time + now,
        }

        if link.is_unique:
            changes["unique_hash"] = urlsafe_short_hash()

        update_withdraw_link(link.id, **changes)

    except ValueError as e:
        return jsonify({"status": "ERROR", "reason": str(e)}), Status.OK
    except PermissionError:
        return jsonify({"status": "ERROR", "reason": "Withdraw link is empty."}), Status.OK
    except Exception as e:
        return jsonify({"status": "ERROR", "reason": str(e)}), Status.OK

    return jsonify({"status": "OK"}), Status.OK
