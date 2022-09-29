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
    with open(os.path.join(LNBITS_PATH, 'extensions/gerty/static/satoshi.json')) as fd:
        satoshiQuotes = json.load(fd)
    return satoshiQuotes[random.randint(0, 100)]


@gerty_ext.get("/api/v1/gerty/pieterwielliequote", status_code=HTTPStatus.OK)
async def api_gerty_wuille():
    with open(os.path.join(LNBITS_PATH, 'extensions/gerty/static/pieter_wuille.json')) as fd:
        data = json.load(fd)
    return data['facts'][random.randint(0, (len(data['facts']) - 1))]


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

    text = await get_screen_text(p, enabled_screens, gerty)

    next_screen_number = 0 if ((p + 1) >= enabled_screen_count) else p + 1;

    # ln = []
    # if gerty.ln_stats and isinstance(gerty.mempool_endpoint, str):
    #     async with httpx.AsyncClient() as client:
    #         r = await client.get(gerty.mempool_endpoint + "/api/v1/lightning/statistics/latest")
    #         if r:
    #             ln.append(r.json())

    return {
        "settings": {
            "refreshTime": gerty.refresh_time,
            "requestTimestamp": round(time.time()),
            "nextScreenNumber": next_screen_number,
            "name": gerty.name
        },
        "screen": {
            "slug": get_screen_slug_by_index(p, enabled_screens),
            "group": get_screen_slug_by_index(p, enabled_screens),
            "text": text
        }
    }


# Get a screen slug by its position in the screens_list
def get_screen_slug_by_index(index: int, screens_list):
    return list(screens_list)[index]


# Get a list of text items for the screen number
async def get_screen_text(screen_num: int, screens_list: dict, gerty):
    screen_slug = get_screen_slug_by_index(screen_num, screens_list)
    # first get the relevant slug from the display_preferences
    logger.debug('screen_slug')
    logger.debug(screen_slug)
    # text = []
    if screen_slug == "lnbits_wallets_balance":
        text = await get_lnbits_wallet_balances(gerty)
    elif screen_slug == "fun_satoshi_quotes":
        text = await get_satoshi_quotes()
    elif screen_slug == "fun_pieter_wuille_facts":
        text = await get_pieter_wuille_fact()
    elif screen_slug == "fun_exchange_market_rate":
        text = await get_exchange_rate(gerty)
    elif screen_slug == "onchain_difficulty_epoch_progress":
        text = await get_onchain_stat(screen_slug, gerty)
    elif screen_slug == "onchain_difficulty_retarget_date":
        text = await get_onchain_stat(screen_slug, gerty)
    elif screen_slug == "onchain_difficulty_blocks_remaining":
        text = await get_onchain_stat(screen_slug, gerty)
    elif screen_slug == "onchain_difficulty_epoch_time_remaining":
        text = await get_onchain_stat(screen_slug, gerty)
    elif screen_slug == "mempool_recommended_fees":
        text = await get_placeholder_text()
    elif screen_slug == "mempool_tx_count":
        text = await get_mempool_stat(screen_slug, gerty)
    elif screen_slug == "mining_current_hash_rate":
        text = await get_placeholder_text()
    elif screen_slug == "mining_current_difficulty":
        text = await get_placeholder_text()
    elif screen_slug == "lightning_channel_count":
        text = await get_placeholder_text()
    elif screen_slug == "lightning_node_count":
        text = await get_placeholder_text()
    elif screen_slug == "lightning_tor_node_count":
        text = await get_placeholder_text()
    elif screen_slug == "lightning_clearnet_nodes":
        text = await get_placeholder_text()
    elif screen_slug == "lightning_unannounced_nodes":
        text = await get_placeholder_text()
    elif screen_slug == "lightning_average_channel_capacity":
        text = await get_placeholder_text()
    return text


async def get_lnbits_wallet_balances(gerty):
    # Get Wallet info
    wallets = []
    text = []
    if gerty.lnbits_wallets != "":
        for lnbits_wallet in json.loads(gerty.lnbits_wallets):

            wallet = await get_wallet_for_key(key=lnbits_wallet)
            logger.debug(wallet)
            if wallet:
                wallets.append({
                    "name": wallet.name,
                    "balance": wallet.balance_msat,
                    "inkey": wallet.inkey,
                })
                text.append(get_text_item_dict(wallet.name, 20))
                text.append(get_text_item_dict(wallet.balance, 40))
    return text


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
            text.append(get_text_item_dict(quote['date'], 15))
    return text


async def get_pieter_wuille_fact():
    text = []
    quote = await api_gerty_wuille()
    if quote:
        text.append(get_text_item_dict(quote, 15))
        text.append(get_text_item_dict("Pieter Wuille facts", 15))
    return text


# Get Exchange Value
async def get_exchange_rate(gerty):
    text = []
    if gerty.exchange != "":
        try:
            amount = await satoshis_amount_as_fiat(100000000, gerty.exchange)
            if amount:
                price = ('{0} {1}').format(format_number(amount), gerty.exchange)
                text.append(get_text_item_dict("Current BTC price", 15))
                text.append(get_text_item_dict(price, 40))
        except:
            pass
    return text


# A helper function get a nicely formated dict for the text
def get_text_item_dict(text: str, font_size: int, x_pos: int = None, y_pos: int = None):
    text = {
        "value": text,
        "size": font_size
    }
    if x_pos is None and y_pos is None:
        text['position'] = 'center'
    else:
        text['x'] = x_pos
        text['y'] = y_pos
    return text


async def get_onchain_stat(stat_slug: str, gerty):
    text = []
    if isinstance(gerty.mempool_endpoint, str):
        async with httpx.AsyncClient() as client:
            if (
                    stat_slug == "onchain_difficulty_epoch_progress" or
                    stat_slug == "onchain_difficulty_retarget_date" or
                    stat_slug == "onchain_difficulty_blocks_remaining" or
                    stat_slug == "onchain_difficulty_epoch_time_remaining"
            ):
                r = await client.get(gerty.mempool_endpoint + "/api/v1/difficulty-adjustment")
                if stat_slug == "onchain_difficulty_epoch_progress":
                    stat = round(r.json()['progressPercent'])
                    text.append(get_text_item_dict("Progress through current difficulty epoch", 15))
                    text.append(get_text_item_dict("{0}%".format(stat), 40))
                elif stat_slug == "onchain_difficulty_retarget_date":
                    stat = r.json()['estimatedRetargetDate']
                    dt = datetime.fromtimestamp(stat / 1000).strftime("%e %b %Y at %H:%M")
                    text.append(get_text_item_dict("Estimated date of next difficulty adjustment", 15))
                    text.append(get_text_item_dict(dt, 40))
                elif stat_slug == "onchain_difficulty_blocks_remaining":
                    stat = r.json()['remainingBlocks']
                    text.append(get_text_item_dict("Blocks remaining until next difficulty adjustment", 15))
                    text.append(get_text_item_dict("{0}".format(format_number(stat)), 40))
                elif stat_slug == "onchain_difficulty_epoch_time_remaining":
                    stat = r.json()['remainingTime']
                    text.append(get_text_item_dict("Blocks remaining until next difficulty adjustment", 15))
                    text.append(get_text_item_dict(get_time_remaining(stat / 1000, 4), 20))
    return text

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
                    text.append(get_text_item_dict("{0}".format(format_number(stat)), 40))
    return text

def get_date_suffix(dayNumber):
    if 4 <= dayNumber <= 20 or 24 <= dayNumber <= 30:
        return "th"
    else:
        return ["st", "nd", "rd"][dayNumber % 10 - 1]

# format a number for nice display output
def format_number(number):
    return ("{:,}".format(round(number)))


def get_time_remaining(seconds, granularity=2):

    intervals = (
        ('weeks', 604800),  # 60 * 60 * 24 * 7
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