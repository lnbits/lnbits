from quart import g, jsonify
from http import HTTPStatus

from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.core.crud import get_wallet, get_wallet_for_key

from . import splitpayments_ext
from .crud import get_targets, set_targets
from .models import Target


@splitpayments_ext.get("/api/v1/targets")
@api_check_wallet_key("admin")
async def api_targets_get():
    targets = await get_targets(g.wallet.id)
    return [target._asdict() for target in targets] or []

class SchemaData(BaseModel):
    wallet:  str
    alias:  str
    percent:  int

@splitpayments_ext.put("/api/v1/targets")
@api_check_wallet_key("admin")
async def api_targets_set(targets: Optional(list[SchemaData]) = None):
    targets = []

    for entry in targets:
        wallet = await get_wallet(entry["wallet"])
        if not wallet:
            wallet = await get_wallet_for_key(entry["wallet"], "invoice")
            if not wallet:
                return (
                    {"message": f"Invalid wallet '{entry['wallet']}'."},
                    HTTPStatus.BAD_REQUEST,
                )

        if wallet.id == g.wallet.id:
            return (
                {"message": "Can't split to itself."},
                HTTPStatus.BAD_REQUEST,
            )

        if entry["percent"] < 0:
            return (
                {"message": f"Invalid percent '{entry['percent']}'."},
                HTTPStatus.BAD_REQUEST,
            )

        targets.append(
            Target(wallet.id, g.wallet.id, entry["percent"], entry["alias"] or "")
        )

    percent_sum = sum([target.percent for target in targets])
    if percent_sum > 100:
        return {"message": "Splitting over 100%."}, HTTPStatus.BAD_REQUEST

    await set_targets(g.wallet.id, targets)
    return "", HTTPStatus.OK
