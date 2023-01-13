import json
from http import HTTPStatus

from fastapi import Depends, Query
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import gerty_ext
from .crud import (
    create_gerty,
    delete_gerty,
    get_gerty,
    get_gertys,
    get_mempool_info,
    update_gerty,
)
from .helpers import (
    gerty_should_sleep,
    get_next_update_time,
    get_satoshi,
    get_screen_data,
    get_screen_slug_by_index,
)
from .models import Gerty


@gerty_ext.get("/api/v1/gerty", status_code=HTTPStatus.OK)
async def api_gertys(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    return [gerty.dict() for gerty in await get_gertys(wallet_ids)]


@gerty_ext.post("/api/v1/gerty", status_code=HTTPStatus.CREATED)
@gerty_ext.put("/api/v1/gerty/{gerty_id}", status_code=HTTPStatus.OK)
async def api_link_create_or_update(
    data: Gerty,
    wallet: WalletTypeInfo = Depends(get_key_type),
    gerty_id: str = Query(None),
):
    if gerty_id:
        gerty = await get_gerty(gerty_id)
        if not gerty:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Gerty does not exist"
            )

        if gerty.wallet != wallet.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Come on, seriously, this isn't your Gerty!",
            )

        data.wallet = wallet.wallet.id
        gerty = await update_gerty(gerty_id, **data.dict())
        assert gerty, HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Gerty does not exist"
        )
    else:
        gerty = await create_gerty(wallet_id=wallet.wallet.id, data=data)

    return {**gerty.dict()}


@gerty_ext.delete("/api/v1/gerty/{gerty_id}")
async def api_gerty_delete(
    gerty_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    gerty = await get_gerty(gerty_id)

    if not gerty:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Gerty does not exist."
        )

    if gerty.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your Gerty.")

    await delete_gerty(gerty_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


@gerty_ext.get("/api/v1/gerty/satoshiquote", status_code=HTTPStatus.OK)
async def api_gerty_satoshi():
    return await get_satoshi()


@gerty_ext.get("/api/v1/gerty/pages/{gerty_id}/{p}")
async def api_gerty_json(gerty_id: str, p: int = 0):  # page number
    gerty = await get_gerty(gerty_id)

    if not gerty:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Gerty does not exist."
        )

    display_preferences = json.loads(gerty.display_preferences)

    enabled_screen_count = 0

    enabled_screens = []

    for screen_slug in display_preferences:
        is_screen_enabled = display_preferences[screen_slug]
        if is_screen_enabled:
            enabled_screen_count += 1
            enabled_screens.append(screen_slug)

    logger.debug("Screens " + str(enabled_screens))
    data = await get_screen_data(p, enabled_screens, gerty)

    next_screen_number = 0 if ((p + 1) >= enabled_screen_count) else p + 1

    # get the sleep time
    sleep_time = gerty.refresh_time if gerty.refresh_time else 300
    utc_offset = gerty.utc_offset if gerty.utc_offset else 0
    if gerty_should_sleep(utc_offset):
        sleep_time_hours = 8
        sleep_time = 60 * 60 * sleep_time_hours

    return {
        "settings": {
            "refreshTime": sleep_time,
            "requestTimestamp": get_next_update_time(sleep_time, utc_offset),
            "nextScreenNumber": next_screen_number,
            "showTextBoundRect": False,
            "name": gerty.name,
        },
        "screen": {
            "slug": get_screen_slug_by_index(p, enabled_screens),
            "group": get_screen_slug_by_index(p, enabled_screens),
            "title": data["title"],
            "areas": data["areas"],
        },
    }


###########CACHED MEMPOOL##############


@gerty_ext.get("/api/v1/gerty/fees-recommended/{gerty_id}")
async def api_gerty_get_fees_recommended(gerty_id):
    gerty = await get_gerty(gerty_id)
    return await get_mempool_info("fees_recommended", gerty)


@gerty_ext.get("/api/v1/gerty/hashrate-1w/{gerty_id}")
async def api_gerty_get_hashrate_1w(gerty_id):
    gerty = await get_gerty(gerty_id)
    return await get_mempool_info("hashrate_1w", gerty)


@gerty_ext.get("/api/v1/gerty/hashrate-1m/{gerty_id}")
async def api_gerty_get_hashrate_1m(gerty_id):
    gerty = await get_gerty(gerty_id)
    return await get_mempool_info("hashrate_1m", gerty)


@gerty_ext.get("/api/v1/gerty/statistics/{gerty_id}")
async def api_gerty_get_statistics(gerty_id):
    gerty = await get_gerty(gerty_id)
    return await get_mempool_info("statistics", gerty)


@gerty_ext.get("/api/v1/gerty/difficulty-adjustment/{gerty_id}")
async def api_gerty_get_difficulty_adjustment(gerty_id):
    gerty = await get_gerty(gerty_id)
    return await get_mempool_info("difficulty_adjustment", gerty)


@gerty_ext.get("/api/v1/gerty/tip-height/{gerty_id}")
async def api_gerty_get_tip_height(gerty_id):
    gerty = await get_gerty(gerty_id)
    return await get_mempool_info("tip_height", gerty)


@gerty_ext.get("/api/v1/gerty/mempool/{gerty_id}")
async def api_gerty_get_mempool(gerty_id):
    gerty = await get_gerty(gerty_id)
    return await get_mempool_info("mempool", gerty)
