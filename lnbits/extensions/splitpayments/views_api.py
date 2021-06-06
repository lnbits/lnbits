from quart import g, jsonify
from http import HTTPStatus

from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.core.crud import get_wallet, get_wallet_for_key

from . import splitpayments_ext
from .crud import get_targets, set_targets
from .models import Target


@splitpayments_ext.route("/api/v1/targets", methods=["GET"])
@api_check_wallet_key("admin")
async def api_targets_get():
    targets = await get_targets(g.wallet.id)
    return jsonify([target._asdict() for target in targets] or [])


@splitpayments_ext.route("/api/v1/targets", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "targets": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": {
                    "wallet": {"type": "string"},
                    "alias": {"type": "string"},
                    "percent": {"type": "integer"},
                },
            },
        }
    }
)
async def api_targets_set():
    targets = []

    for entry in g.data["targets"]:
        wallet = await get_wallet(entry["wallet"])
        if not wallet:
            wallet = await get_wallet_for_key(entry["wallet"], "invoice")
            if not wallet:
                return (
                    jsonify({"message": f"Invalid wallet '{entry['wallet']}'."}),
                    HTTPStatus.BAD_REQUEST,
                )

        if wallet.id == g.wallet.id:
            return (
                jsonify({"message": "Can't split to itself."}),
                HTTPStatus.BAD_REQUEST,
            )

        if entry["percent"] < 0:
            return (
                jsonify({"message": f"Invalid percent '{entry['percent']}'."}),
                HTTPStatus.BAD_REQUEST,
            )

        targets.append(
            Target(wallet.id, g.wallet.id, entry["percent"], entry["alias"] or "")
        )

    percent_sum = sum([target.percent for target in targets])
    if percent_sum > 100:
        return jsonify({"message": "Splitting over 100%."}), HTTPStatus.BAD_REQUEST

    await set_targets(g.wallet.id, targets)
    return "", HTTPStatus.OK
