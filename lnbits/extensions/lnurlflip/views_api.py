from quart import g, jsonify, request
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import lnurlflip_ext
from .crud import (
    create_lnurlflip_link,
    get_lnurlflip_link,
    get_lnurlflip_links,
    update_lnurlflip_link,
    delete_lnurlflip_link,
    create_hash_check,
    get_hash_check,
)


@lnurlflip_ext.route("/api/v1/links", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_links():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    try:
        return (
            jsonify(
                [
                    {
                        **link._asdict(),
                        **{"lnurl": link.lnurl},
                    }
                    for link in await get_lnurlflip_links(wallet_ids)
                ]
            ),
            HTTPStatus.OK,
        )
    except LnurlInvalidUrl:
        return (
            jsonify(
                {
                    "message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor."
                }
            ),
            HTTPStatus.UPGRADE_REQUIRED,
        )


@lnurlflip_ext.route("/api/v1/links/<link_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_link_retrieve(link_id):
    link = await get_lnurlflip_link(link_id, 0)

    if not link:
        return (
            jsonify({"message": "lnurlflip link does not exist."}),
            HTTPStatus.NOT_FOUND,
        )

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your lnurlflip link."}), HTTPStatus.FORBIDDEN

    return jsonify({**link._asdict(), **{"lnurl": link.lnurl}}), HTTPStatus.OK


@lnurlflip_ext.route("/api/v1/links", methods=["POST"])
@lnurlflip_ext.route("/api/v1/links/<link_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "title": {"type": "string", "empty": False, "required": True},
        "min_lnurlflipable": {"type": "integer", "min": 1, "required": True},
        "max_lnurlflipable": {"type": "integer", "min": 1, "required": True},
        "uses": {"type": "integer", "min": 1, "required": True},
        "wait_time": {"type": "integer", "min": 1, "required": True},
        "is_unique": {"type": "boolean", "required": True},
    }
)
async def api_link_create_or_update(link_id=None):
    if g.data["max_lnurlflipable"] < g.data["min_lnurlflipable"]:
        return (
            jsonify(
                {
                    "message": "`max_lnurlflipable` needs to be at least `min_lnurlflipable`."
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )

    usescsv = ""
    for i in range(g.data["uses"]):
        if g.data["is_unique"]:
            usescsv += "," + str(i + 1)
        else:
            usescsv += "," + str(1)
    usescsv = usescsv[1:]

    if link_id:
        link = await get_lnurlflip_link(link_id, 0)
        if not link:
            return (
                jsonify({"message": "lnurlflip link does not exist."}),
                HTTPStatus.NOT_FOUND,
            )
        if link.wallet != g.wallet.id:
            return (
                jsonify({"message": "Not your lnurlflip link."}),
                HTTPStatus.FORBIDDEN,
            )
        link = await update_lnurlflip_link(link_id, **g.data, usescsv=usescsv, used=0)
    else:
        link = await create_lnurlflip_link(
            wallet_id=g.wallet.id, **g.data, usescsv=usescsv
        )

    return (
        jsonify({**link._asdict(), **{"lnurl": link.lnurl}}),
        HTTPStatus.OK if link_id else HTTPStatus.CREATED,
    )


@lnurlflip_ext.route("/api/v1/links/<link_id>", methods=["DELETE"])
@api_check_wallet_key("admin")
async def api_link_delete(link_id):
    link = await get_lnurlflip_link(link_id)

    if not link:
        return (
            jsonify({"message": "lnurlflip link does not exist."}),
            HTTPStatus.NOT_FOUND,
        )

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your lnurlflip link."}), HTTPStatus.FORBIDDEN

    await delete_lnurlflip_link(link_id)

    return "", HTTPStatus.NO_CONTENT


@lnurlflip_ext.route("/api/v1/links/<the_hash>/<lnurl_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_hash_retrieve(the_hash, lnurl_id):
    hashCheck = await get_hash_check(the_hash, lnurl_id)
    return jsonify(hashCheck), HTTPStatus.OK
