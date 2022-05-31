import hashlib
from quart import g, jsonify, url_for
from http import HTTPStatus
import httpx


from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from lnbits.extensions.satspay import satspay_ext
from .crud import (
    create_charge,
    update_charge,
    get_charge,
    get_charges,
    delete_charge,
    check_address_balance,
)

#############################CHARGES##########################


@satspay_ext.route("/api/v1/charge", methods=["POST"])
@satspay_ext.route("/api/v1/charge/<charge_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "onchainwallet": {"type": "string"},
        "lnbitswallet": {"type": "string"},
        "description": {"type": "string", "empty": False, "required": True},
        "webhook": {"type": "string"},
        "completelink": {"type": "string"},
        "completelinktext": {"type": "string"},
        "time": {"type": "integer", "min": 1, "required": True},
        "amount": {"type": "integer", "min": 1, "required": True},
    }
)
async def api_charge_create_or_update(charge_id=None):
    if not charge_id:
        charge = await create_charge(user=g.wallet.user, **g.data)
        return jsonify(charge._asdict()), HTTPStatus.CREATED
    else:
        charge = await update_charge(charge_id=charge_id, **g.data)
        return jsonify(charge._asdict()), HTTPStatus.OK


@satspay_ext.route("/api/v1/charges", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_charges_retrieve():
    try:
        return (
            jsonify(
                [
                    {
                        **charge._asdict(),
                        **{"time_elapsed": charge.time_elapsed},
                        **{"paid": charge.paid},
                    }
                    for charge in await get_charges(g.wallet.user)
                ]
            ),
            HTTPStatus.OK,
        )
    except:
        return ""


@satspay_ext.route("/api/v1/charge/<charge_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_charge_retrieve(charge_id):
    charge = await get_charge(charge_id)

    if not charge:
        return jsonify({"message": "charge does not exist"}), HTTPStatus.NOT_FOUND

    return (
        jsonify(
            {
                **charge._asdict(),
                **{"time_elapsed": charge.time_elapsed},
                **{"paid": charge.paid},
            }
        ),
        HTTPStatus.OK,
    )


@satspay_ext.route("/api/v1/charge/<charge_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_charge_delete(charge_id):
    charge = await get_charge(charge_id)

    if not charge:
        return jsonify({"message": "Wallet link does not exist."}), HTTPStatus.NOT_FOUND

    await delete_charge(charge_id)

    return "", HTTPStatus.NO_CONTENT


#############################BALANCE##########################


@satspay_ext.route("/api/v1/charges/balance/<charge_id>", methods=["GET"])
async def api_charges_balance(charge_id):

    charge = await check_address_balance(charge_id)

    if not charge:
        return jsonify({"message": "charge does not exist"}), HTTPStatus.NOT_FOUND
    if charge.paid and charge.webhook:
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(
                    charge.webhook,
                    json={
                        "id": charge.id,
                        "description": charge.description,
                        "onchainaddress": charge.onchainaddress,
                        "payment_request": charge.payment_request,
                        "payment_hash": charge.payment_hash,
                        "time": charge.time,
                        "amount": charge.amount,
                        "balance": charge.balance,
                        "paid": charge.paid,
                        "timestamp": charge.timestamp,
                        "completelink": charge.completelink,
                    },
                    timeout=40,
                )
            except AssertionError:
                charge.webhook = None
    return jsonify(charge._asdict()), HTTPStatus.OK


#############################MEMPOOL##########################


@satspay_ext.route("/api/v1/mempool", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "endpoint": {"type": "string", "empty": False, "required": True},
    }
)
async def api_update_mempool():
    mempool = await update_mempool(user=g.wallet.user, **g.data)
    return jsonify(mempool._asdict()), HTTPStatus.OK


@satspay_ext.route("/api/v1/mempool", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_get_mempool():
    mempool = await get_mempool(g.wallet.user)
    if not mempool:
        mempool = await create_mempool(user=g.wallet.user)
    return jsonify(mempool._asdict()), HTTPStatus.OK
