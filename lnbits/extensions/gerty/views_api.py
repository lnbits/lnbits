import math
from http import HTTPStatus
import json
import httpx
import random
import os
import time
from datetime import datetime
from fastapi import Query
from fastapi.params import Depends
from lnurl import decode as decode_lnurl
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_wallet_for_key
from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment, api_wallet
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from fastapi.templating import Jinja2Templates

from .helpers import *

from . import gerty_ext
from .crud import create_gerty, update_gerty, delete_gerty, get_gerty, get_gertys
from .models import Gerty

from lnbits.utils.exchange_rates import satoshis_amount_as_fiat
from ...settings import LNBITS_PATH


@gerty_ext.get("/api/v1/gerty", status_code=HTTPStatus.OK)
async def api_gertys(
        all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

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


#######################

@gerty_ext.get("/api/v1/gerty/satoshiquote", status_code=HTTPStatus.OK)
async def api_gerty_satoshi():
    maxQuoteLength = 186;
    with open(os.path.join(LNBITS_PATH, 'extensions/gerty/static/satoshi.json')) as fd:
        satoshiQuotes = json.load(fd)
    quote = satoshiQuotes[random.randint(0, len(satoshiQuotes) - 1)]
    # logger.debug(quote.text)
    if len(quote["text"]) > maxQuoteLength:
        logger.debug("Quote is too long, getting another")
        return await api_gerty_satoshi()
    else:
        return quote


@gerty_ext.get("/api/v1/gerty/{gerty_id}/{p}")
async def api_gerty_json(
        gerty_id: str,
        p: int = None  # page number
):
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

    logger.debug("Screeens " + str(enabled_screens))
    data = await get_screen_data(p, enabled_screens, gerty)

    next_screen_number = 0 if ((p + 1) >= enabled_screen_count) else p + 1;

    # get the sleep time
    sleep_time = gerty.refresh_time if gerty.refresh_time else 300
    if gerty_should_sleep():
        sleep_time_hours = 8
        sleep_time = 60 * 60 * sleep_time_hours

    return {
        "settings": {
            "refreshTime": sleep_time,
            "requestTimestamp": get_next_update_time(sleep_time),
            "nextScreenNumber": next_screen_number,
            "showTextBoundRect": False,
            "name": gerty.name
        },
        "screen": {
            "slug": get_screen_slug_by_index(p, enabled_screens),
            "group": get_screen_slug_by_index(p, enabled_screens),
            "title": data['title'],
            "areas": data['areas']
        }
    }


# Get a screen slug by its position in the screens_list
def get_screen_slug_by_index(index: int, screens_list):
    return list(screens_list)[index]


# Get a list of text items for the screen number
async def get_screen_data(screen_num: int, screens_list: dict, gerty):
    screen_slug = get_screen_slug_by_index(screen_num, screens_list)
    # first get the relevant slug from the display_preferences
    logger.debug('screen_slug')
    logger.debug(screen_slug)
    areas = []
    title = ""

    if screen_slug == "dashboard":
        title = gerty.name
        areas = await get_dashboard(gerty)
    elif screen_slug == "fun_satoshi_quotes":
        areas.append(await get_satoshi_quotes())
    elif screen_slug == "fun_exchange_market_rate":
        areas.append(await get_exchange_rate(gerty))
    elif screen_slug == "onchain_dashboard":
        areas.append(await get_onchain_dashboard(gerty))
    elif screen_slug == "mempool_recommended_fees":
        areas.append(await get_mempool_stat(screen_slug, gerty))
    elif screen_slug == "mempool_tx_count":
        areas.append(await get_mempool_stat(screen_slug, gerty))
    elif screen_slug == "mining_current_hash_rate":
        areas.append(await get_mining_stat(screen_slug, gerty))
    elif screen_slug == "mining_current_difficulty":
        areas.append(await get_mining_stat(screen_slug, gerty))
    elif screen_slug == "lightning_dashboard":
        title = "Lightning Network"
        areas = await get_lightning_stats(gerty)

    data = {}
    data['title'] = title
    data['areas'] = areas

    return data


# Get the dashboard screen
async def get_dashboard(gerty):
    areas = []
    # XC rate
    text = []
    amount = await satoshis_amount_as_fiat(100000000, gerty.exchange)
    text.append(get_text_item_dict(format_number(amount), 40))
    text.append(get_text_item_dict("BTC{0} price".format(gerty.exchange), 15))
    areas.append(text)
    # balance
    text = []
    wallets = await get_lnbits_wallet_balances(gerty)
    text = []
    for wallet in wallets:
        text.append(get_text_item_dict("{0}".format(wallet['name']), 15))
        text.append(get_text_item_dict("{0} sats".format(format_number(wallet['balance'])), 20))
    areas.append(text)

    # Mempool fees
    text = []
    text.append(get_text_item_dict(format_number(await get_block_height(gerty)), 40))
    text.append(get_text_item_dict("Current block height", 15))
    areas.append(text)

    # difficulty adjustment time
    text = []
    text.append(get_text_item_dict(await get_time_remaining_next_difficulty_adjustment(gerty), 15))
    text.append(get_text_item_dict("until next difficulty adjustment", 12))
    areas.append(text)

    return areas


async def get_lnbits_wallet_balances(gerty):
    # Get Wallet info
    wallets = []
    if gerty.lnbits_wallets != "":
        for lnbits_wallet in json.loads(gerty.lnbits_wallets):
            wallet = await get_wallet_for_key(key=lnbits_wallet)
            logger.debug(wallet.name)
            if wallet:
                wallets.append({
                    "name": wallet.name,
                    "balance": wallet.balance_msat / 1000,
                    "inkey": wallet.inkey,
                })
    return wallets


async def get_placeholder_text():
    return [
        get_text_item_dict("Some placeholder text", 15, 10, 50),
        get_text_item_dict("Some placeholder text", 15, 10, 50)
    ]


async def get_satoshi_quotes():
    # Get Satoshi quotes
    text = []
    quote = await api_gerty_satoshi()
    if quote:
        if quote['text']:
            text.append(get_text_item_dict(quote['text'], 15))
        if quote['date']:
            text.append(get_text_item_dict("Satoshi Nakamoto - {0}".format(quote['date']), 15))
    return text


# Get Exchange Value
async def get_exchange_rate(gerty):
    text = []
    if gerty.exchange != "":
        try:
            amount = await satoshis_amount_as_fiat(100000000, gerty.exchange)
            if amount:
                price = format_number(amount)
                text.append(get_text_item_dict("Current {0}/BTC price".format(gerty.exchange), 15))
                text.append(get_text_item_dict(price, 80))
        except:
            pass
    return text


async def get_onchain_dashboard(gerty):
    areas = []
    if isinstance(gerty.mempool_endpoint, str):
        async with httpx.AsyncClient() as client:
            r = await client.get(gerty.mempool_endpoint + "/api/v1/difficulty-adjustment")
            text = []
            stat = round(r.json()['progressPercent'])
            text.append(get_text_item_dict("Progress through current difficulty epoch", 12))
            text.append(get_text_item_dict("{0}%".format(stat), 20))
            areas.append(text)

            text = []
            stat = r.json()['estimatedRetargetDate']
            dt = datetime.fromtimestamp(stat / 1000).strftime("%e %b %Y at %H:%M")
            text.append(get_text_item_dict("Estimated date of next difficulty adjustment", 12))
            text.append(get_text_item_dict(dt, 20))
            areas.append(text)

            text = []
            stat = r.json()['remainingBlocks']
            text.append(get_text_item_dict("Blocks remaining until next difficulty adjustment", 12))
            text.append(get_text_item_dict("{0}".format(format_number(stat)), 20))
            areas.append(text)

            text = []
            stat = r.json()['remainingTime']
            text.append(get_text_item_dict("Blocks remaining until next difficulty adjustment", 12))
            text.append(get_text_item_dict(get_time_remaining(stat / 1000, 4), 20))
            areas.append(text)

    return areas

async def get_time_remaining_next_difficulty_adjustment(gerty):
    if isinstance(gerty.mempool_endpoint, str):
        async with httpx.AsyncClient() as client:
            r = await client.get(gerty.mempool_endpoint + "/api/v1/difficulty-adjustment")
            stat = r.json()['remainingTime']
            time = get_time_remaining(stat / 1000, 3)
    return time


async def get_block_height(gerty):
    if isinstance(gerty.mempool_endpoint, str):
        async with httpx.AsyncClient() as client:
            r = await client.get(gerty.mempool_endpoint + "/api/blocks/tip/height")

    return r.json()


async def get_mempool_stat(stat_slug: str, gerty):
    text = []
    if isinstance(gerty.mempool_endpoint, str):
        async with httpx.AsyncClient() as client:
            if (
                    stat_slug == "mempool_tx_count"
            ):
                r = await client.get(gerty.mempool_endpoint + "/api/mempool")
                if stat_slug == "mempool_tx_count":
                    stat = round(r.json()['count'])
                    text.append(get_text_item_dict("Transactions in the mempool", 15))
                    text.append(get_text_item_dict("{0}".format(format_number(stat)), 80))
            elif (
                    stat_slug == "mempool_recommended_fees"
            ):
                y_offset = 60
                fees = await get_mempool_recommended_fees(gerty)
                pos_y = 80 + y_offset
                text.append(get_text_item_dict("mempool.space", 40, 160, pos_y))
                pos_y = 180 + y_offset
                text.append(get_text_item_dict("Recommended Tx Fees", 20, 240, pos_y))

                pos_y = 280 + y_offset
                text.append(get_text_item_dict("{0}".format("No Priority"), 15, 30, pos_y))
                text.append(get_text_item_dict("{0}".format("Low Priority"), 15, 235, pos_y))
                text.append(get_text_item_dict("{0}".format("Medium Priority"), 15, 460, pos_y))
                text.append(get_text_item_dict("{0}".format("High Priority"), 15, 750, pos_y))

                pos_y = 340 + y_offset
                font_size = 15
                fee_append = "/vB"
                fee_rate = fees["economyFee"]
                text.append(get_text_item_dict(
                    "{0} {1}{2}".format(format_number(fee_rate), ("sat" if fee_rate == 1 else "sats"), fee_append),
                    font_size,
                    30, pos_y))

                fee_rate = fees["hourFee"]
                text.append(get_text_item_dict(
                    "{0} {1}{2}".format(format_number(fee_rate), ("sat" if fee_rate == 1 else "sats"), fee_append),
                    font_size,
                    235, pos_y))

                fee_rate = fees["halfHourFee"]
                text.append(get_text_item_dict(
                    "{0} {1}{2}".format(format_number(fee_rate), ("sat" if fee_rate == 1 else "sats"), fee_append),
                    font_size,
                    460, pos_y))

                fee_rate = fees["fastestFee"]
                text.append(get_text_item_dict(
                    "{0} {1}{2}".format(format_number(fee_rate), ("sat" if fee_rate == 1 else "sats"), fee_append),
                    font_size,
                    750, pos_y))
    return text


def get_date_suffix(dayNumber):
    if 4 <= dayNumber <= 20 or 24 <= dayNumber <= 30:
        return "th"
    else:
        return ["st", "nd", "rd"][dayNumber % 10 - 1]


def get_time_remaining(seconds, granularity=2):
    intervals = (
        # ('weeks', 604800),  # 60 * 60 * 24 * 7
        ('days', 86400),  # 60 * 60 * 24
        ('hours', 3600),  # 60 * 60
        ('minutes', 60),
        ('seconds', 1),
    )

    result = []

    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(round(value), name))
    return ', '.join(result[:granularity])
