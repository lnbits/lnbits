import hashlib
from quart import g, jsonify, url_for
from http import HTTPStatus
import httpx


from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from lnbits.extensions.satspay import satspay_ext
from .crud import (
    create_charge,
    get_charge,
    get_charges,
    delete_charge,
)

###################WALLETS#############################

@satspay_ext.route("/api/v1/wallet", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_wallets_retrieve():

    try:
        return (
            jsonify([wallet._asdict() for wallet in await get_watch_wallets(g.wallet.user)]), HTTPStatus.OK
        )
    except:
        return ""

@satspay_ext.route("/api/v1/wallet/<wallet_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_wallet_retrieve(wallet_id):
    wallet = await get_watch_wallet(wallet_id) 
        
    if not wallet:
        return jsonify({"message": "wallet does not exist"}), HTTPStatus.NOT_FOUND

    return jsonify({wallet}), HTTPStatus.OK


@satspay_ext.route("/api/v1/wallet", methods=["POST"])
@satspay_ext.route("/api/v1/wallet/<wallet_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "masterpub": {"type": "string", "empty": False, "required": True},
        "title": {"type": "string", "empty": False, "required": True},
    }
)
async def api_wallet_create_or_update(wallet_id=None):
    print("g.data")
    if not wallet_id:
        wallet = await create_watch_wallet(user=g.wallet.user, masterpub=g.data["masterpub"], title=g.data["title"])
        mempool = await get_mempool(g.wallet.user) 
        if not mempool:
            create_mempool(user=g.wallet.user)
        return jsonify(wallet._asdict()), HTTPStatus.CREATED
    else:
        wallet = await update_watch_wallet(wallet_id=wallet_id, **g.data) 
        return jsonify(wallet._asdict()), HTTPStatus.OK 


@satspay_ext.route("/api/v1/wallet/<wallet_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_wallet_delete(wallet_id):
    wallet = await get_watch_wallet(wallet_id)

    if not wallet:
        return jsonify({"message": "Wallet link does not exist."}), HTTPStatus.NOT_FOUND

    await delete_watch_wallet(wallet_id)

    return jsonify({"deleted": "true"}), HTTPStatus.NO_CONTENT


#############################CHARGES##########################

@satspay_ext.route("/api/v1/charges", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_charges_retrieve():

    charges = await get_charges(g.wallet.user)
    print(charges)
    if not charges:
        return (
            jsonify(""),
            HTTPStatus.OK
        )
    else:
        return jsonify([charge._asdict() for charge in charges]), HTTPStatus.OK


@satspay_ext.route("/api/v1/charge/<charge_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_charge_retrieve(charge_id):
    charge = get_charge(charge_id) 
        
    if not charge:
        return jsonify({"message": "charge does not exist"}), HTTPStatus.NOT_FOUND

    return jsonify({charge}), HTTPStatus.OK


@satspay_ext.route("/api/v1/charge", methods=["POST"])
@satspay_ext.route("/api/v1/charge/<charge_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "onchainwallet": {"type": "string", "empty": False, "required": True},
        "lnbitswallet": {"type": "string", "empty": False, "required": True},
        "description": {"type": "string", "empty": False, "required": True},
        "webhook": {"type": "string", "empty": False, "required": True},
        "time": {"type": "integer", "min": 1, "required": True},
        "amount": {"type": "integer", "min": 1, "required": True},
    }
)
async def api_charge_create_or_update(charge_id=None):

    if not charge_id:
        charge = await create_charge(user = g.wallet.user, **g.data)
        return jsonify(charge), HTTPStatus.CREATED
    else:
        charge = await update_charge(user = g.wallet.user, **g.data) 
        return jsonify(charge), HTTPStatus.OK 


@satspay_ext.route("/api/v1/charge/<charge_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_charge_delete(charge_id):
    charge = await get_watch_wallet(charge_id)

    if not charge:
        return jsonify({"message": "Wallet link does not exist."}), HTTPStatus.NOT_FOUND

    await delete_watch_wallet(charge_id)

    return "", HTTPStatus.NO_CONTENT

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