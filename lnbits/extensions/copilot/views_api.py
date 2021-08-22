import hashlib
from quart import g, jsonify, url_for, websocket
from http import HTTPStatus
import httpx

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from .views import updater

from . import copilot_ext

from lnbits.extensions.copilot import copilot_ext
from .crud import (
    create_copilot,
    update_copilot,
    get_copilot,
    get_copilots,
    delete_copilot,
)

#######################COPILOT##########################

class CreateData(BaseModel):
    title:  str
    lnurl_toggle:  Optional[int]
    wallet:  Optional[str]
    animation1:  Optional[str]
    animation2:  Optional[str] 
    animation3:  Optional[str]
    animation1threshold:  Optional[int]
    animation2threshold:  Optional[int]
    animation2threshold:  Optional[int]
    animation1webhook:  Optional[str]
    animation2webhook:  Optional[str] 
    animation3webhook:  Optional[str]
    lnurl_title:  Optional[str]
    show_message:  Optional[int]
    show_ack:  Optional[int]
    show_price:  Optional[str]

@copilot_ext.post("/api/v1/copilot")
@copilot_ext.put("/api/v1/copilot/{copilot_id}")
@api_check_wallet_key("admin")
async def api_copilot_create_or_update(data: CreateData,copilot_id=None):
    if not copilot_id:
        copilot = await create_copilot(user=g.wallet.user, **data)
        return jsonify(copilot._asdict()), HTTPStatus.CREATED
    else:
        copilot = await update_copilot(copilot_id=copilot_id, **data)
        return jsonify(copilot._asdict()), HTTPStatus.OK


@copilot_ext.get("/api/v1/copilot")
@api_check_wallet_key("invoice")
async def api_copilots_retrieve():
    try:
        return (
                [{**copilot._asdict()} for copilot in await get_copilots(g.wallet.user)],
            HTTPStatus.OK,
        )
    except:
        return ""


@copilot_ext.get("/api/v1/copilot/{copilot_id}")
@api_check_wallet_key("invoice")
async def api_copilot_retrieve(copilot_id):
    copilot = await get_copilot(copilot_id)
    if not copilot:
        return {"message": "copilot does not exist"}, HTTPStatus.NOT_FOUND
    if not copilot.lnurl_toggle:
        return (
            {**copilot._asdict()},
            HTTPStatus.OK,
        )
    return (
        {**copilot._asdict(), **{"lnurl": copilot.lnurl}},
        HTTPStatus.OK,
    )


@copilot_ext.delete("/api/v1/copilot/{copilot_id}")
@api_check_wallet_key("admin")
async def api_copilot_delete(copilot_id):
    copilot = await get_copilot(copilot_id)

    if not copilot:
        return {"message": "Wallet link does not exist."}, HTTPStatus.NOT_FOUND

    await delete_copilot(copilot_id)

    return "", HTTPStatus.NO_CONTENT


@copilot_ext.get("/api/v1/copilot/ws/{copilot_id}/{comment}/{data}")
async def api_copilot_ws_relay(copilot_id, comment, data):
    copilot = await get_copilot(copilot_id)
    if not copilot:
        return {"message": "copilot does not exist"}, HTTPStatus.NOT_FOUND
    try:
        await updater(copilot_id, data, comment)
    except:
        return "", HTTPStatus.FORBIDDEN
    return "", HTTPStatus.OK
