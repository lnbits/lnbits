import json
import os
import random
import textwrap
from datetime import datetime, timedelta
from typing import List

import httpx
from loguru import logger

from lnbits.core.crud import get_wallet_for_key
from lnbits.settings import settings
from lnbits.utils.exchange_rates import satoshis_amount_as_fiat

from .crud import get_mempool_info
from .number_prefixer import *


def get_percent_difference(current, previous, precision=3):
    difference = (current - previous) / current * 100
    return "{0}{1}%".format("+" if difference > 0 else "", round(difference, precision))


# A helper function get a nicely formated dict for the text
def get_text_item_dict(
    text: str,
    font_size: int,
    x_pos: int = -1,
    y_pos: int = -1,
    gerty_type: str = "Gerty",
):
    # Get line size by font size
    line_width = 20
    if font_size <= 12:
        line_width = 60
    elif font_size <= 15:
        line_width = 45
    elif font_size <= 20:
        line_width = 35
    elif font_size <= 40:
        line_width = 25

    #  wrap the text
    wrapper = textwrap.TextWrapper(width=line_width)
    word_list = wrapper.wrap(text=text)
    # logger.debug("number of chars = {0}".format(len(text)))

    multilineText = "\n".join(word_list)
    # logger.debug("number of lines = {0}".format(len(word_list)))

    # logger.debug('multilineText')
    # logger.debug(multilineText)

    data_text = {"value": multilineText, "size": font_size}
    if x_pos == -1 and y_pos == -1:
        data_text["position"] = "center"
    else:
        data_text["x"] = x_pos if x_pos > 0 else 0
        data_text["y"] = y_pos if x_pos > 0 else 0
    return data_text


def get_date_suffix(dayNumber):
    if 4 <= dayNumber <= 20 or 24 <= dayNumber <= 30:
        return "th"
    else:
        return ["st", "nd", "rd"][dayNumber % 10 - 1]


def get_time_remaining(seconds, granularity=2):
    intervals = (
        # ('weeks', 604800),  # 60 * 60 * 24 * 7
        ("days", 86400),  # 60 * 60 * 24
        ("hours", 3600),  # 60 * 60
        ("minutes", 60),
        ("seconds", 1),
    )

    result = []

    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip("s")
            result.append("{} {}".format(round(value), name))
    return ", ".join(result[:granularity])


# format a number for nice display output
def format_number(number, precision=None):
    return "{:,}".format(round(number, precision))


async def get_mining_dashboard(gerty):
    areas = []
    if isinstance(gerty.mempool_endpoint, str):
        # current hashrate
        r = await get_mempool_info("hashrate_1w", gerty)
        data = r
        hashrateNow = data["currentHashrate"]
        hashrateOneWeekAgo = data["hashrates"][6]["avgHashrate"]

        text = []
        text.append(
            get_text_item_dict(
                text="Current hashrate", font_size=12, gerty_type=gerty.type
            )
        )
        text.append(
            get_text_item_dict(
                text="{0}hash".format(si_format(hashrateNow, 6, True, " ")),
                font_size=20,
                gerty_type=gerty.type,
            )
        )
        text.append(
            get_text_item_dict(
                text="{0} vs 7 days ago".format(
                    get_percent_difference(hashrateNow, hashrateOneWeekAgo, 3)
                ),
                font_size=12,
                gerty_type=gerty.type,
            )
        )
        areas.append(text)

        r = await get_mempool_info("difficulty_adjustment", gerty)

        # timeAvg
        text = []
        progress = "{0}%".format(round(r["progressPercent"], 2))
        text.append(
            get_text_item_dict(
                text="Progress through current epoch",
                font_size=12,
                gerty_type=gerty.type,
            )
        )
        text.append(
            get_text_item_dict(text=progress, font_size=40, gerty_type=gerty.type)
        )
        areas.append(text)

        # difficulty adjustment
        text = []
        stat = r["remainingTime"]
        text.append(
            get_text_item_dict(
                text="Time to next difficulty adjustment",
                font_size=12,
                gerty_type=gerty.type,
            )
        )
        text.append(
            get_text_item_dict(
                text=get_time_remaining(stat / 1000, 3),
                font_size=12,
                gerty_type=gerty.type,
            )
        )
        areas.append(text)

        # difficultyChange
        text = []
        difficultyChange = round(r["difficultyChange"], 2)
        text.append(
            get_text_item_dict(
                text="Estimated difficulty change",
                font_size=12,
                gerty_type=gerty.type,
            )
        )
        text.append(
            get_text_item_dict(
                text="{0}{1}%".format(
                    "+" if difficultyChange > 0 else "", round(difficultyChange, 2)
                ),
                font_size=40,
                gerty_type=gerty.type,
            )
        )
        areas.append(text)

        r = await get_mempool_info("hashrate_1m", gerty)
        data = r
        stat = {}
        stat["current"] = data["currentDifficulty"]
        stat["previous"] = data["difficulty"][len(data["difficulty"]) - 2]["difficulty"]
    return areas


async def get_lightning_stats(gerty):
    data = await get_mempool_info("statistics", gerty)
    areas = []

    text = []
    text.append(
        get_text_item_dict(text="Channel Count", font_size=12, gerty_type=gerty.type)
    )
    text.append(
        get_text_item_dict(
            text=format_number(data["latest"]["channel_count"]),
            font_size=20,
            gerty_type=gerty.type,
        )
    )
    difference = get_percent_difference(
        current=data["latest"]["channel_count"],
        previous=data["previous"]["channel_count"],
    )
    text.append(
        get_text_item_dict(
            text="{0} in last 7 days".format(difference),
            font_size=12,
            gerty_type=gerty.type,
        )
    )
    areas.append(text)

    text = []
    text.append(
        get_text_item_dict(text="Number of Nodes", font_size=12, gerty_type=gerty.type)
    )
    text.append(
        get_text_item_dict(
            text=format_number(data["latest"]["node_count"]),
            font_size=20,
            gerty_type=gerty.type,
        )
    )
    difference = get_percent_difference(
        current=data["latest"]["node_count"], previous=data["previous"]["node_count"]
    )
    text.append(
        get_text_item_dict(
            text="{0} in last 7 days".format(difference),
            font_size=12,
            gerty_type=gerty.type,
        )
    )
    areas.append(text)

    text = []
    text.append(
        get_text_item_dict(text="Total Capacity", font_size=12, gerty_type=gerty.type)
    )
    avg_capacity = float(data["latest"]["total_capacity"]) / float(100000000)
    text.append(
        get_text_item_dict(
            text="{0} BTC".format(format_number(avg_capacity, 2)),
            font_size=20,
            gerty_type=gerty.type,
        )
    )
    difference = get_percent_difference(
        current=data["latest"]["total_capacity"],
        previous=data["previous"]["total_capacity"],
    )
    text.append(
        get_text_item_dict(
            text="{0} in last 7 days".format(difference),
            font_size=12,
            gerty_type=gerty.type,
        )
    )
    areas.append(text)

    text = []
    text.append(
        get_text_item_dict(
            text="Average Channel Capacity", font_size=12, gerty_type=gerty.type
        )
    )
    text.append(
        get_text_item_dict(
            text="{0} sats".format(format_number(data["latest"]["avg_capacity"])),
            font_size=20,
            gerty_type=gerty.type,
        )
    )
    difference = get_percent_difference(
        current=data["latest"]["avg_capacity"],
        previous=data["previous"]["avg_capacity"],
    )
    text.append(
        get_text_item_dict(
            text="{0} in last 7 days".format(difference),
            font_size=12,
            gerty_type=gerty.type,
        )
    )
    areas.append(text)

    return areas


def get_next_update_time(sleep_time_seconds: int = 0, utc_offset: int = 0):
    utc_now = datetime.utcnow()
    next_refresh_time = utc_now + timedelta(0, sleep_time_seconds)
    local_refresh_time = next_refresh_time + timedelta(hours=utc_offset)
    return "{0} {1}".format(
        "I'll wake up at" if gerty_should_sleep(utc_offset) else "Next update at",
        local_refresh_time.strftime("%H:%M"),
    )


def gerty_should_sleep(utc_offset: int = 0):
    utc_now = datetime.utcnow()
    local_time = utc_now + timedelta(hours=utc_offset)
    hours = int(local_time.strftime("%H"))
    if hours >= 22 and hours <= 23:
        return True
    else:
        return False


async def get_mining_stat(stat_slug: str, gerty):
    text = []
    if stat_slug == "mining_current_hash_rate":
        stat = await api_get_mining_stat(stat_slug, gerty)
        current = "{0}hash".format(si_format(stat["current"], 6, True, " "))
        text.append(
            get_text_item_dict(
                text="Current Mining Hashrate", font_size=20, gerty_type=gerty.type
            )
        )
        text.append(
            get_text_item_dict(text=current, font_size=40, gerty_type=gerty.type)
        )
        # compare vs previous time period
        difference = get_percent_difference(
            current=stat["current"], previous=stat["1w"]
        )
        text.append(
            get_text_item_dict(
                text="{0} in last 7 days".format(difference),
                font_size=12,
                gerty_type=gerty.type,
            )
        )
    elif stat_slug == "mining_current_difficulty":
        stat = await api_get_mining_stat(stat_slug, gerty)
        text.append(
            get_text_item_dict(
                text="Current Mining Difficulty", font_size=20, gerty_type=gerty.type
            )
        )
        text.append(
            get_text_item_dict(
                text=format_number(stat["current"]), font_size=40, gerty_type=gerty.type
            )
        )
        difference = get_percent_difference(
            current=stat["current"], previous=stat["previous"]
        )
        text.append(
            get_text_item_dict(
                text="{0} since last adjustment".format(difference),
                font_size=12,
                gerty_type=gerty.type,
            )
        )
        # text.append(get_text_item_dict("Required threshold for mining proof-of-work", 12))
    return text


async def api_get_mining_stat(stat_slug: str, gerty):
    stat = {}
    if stat_slug == "mining_current_hash_rate":
        r = await get_mempool_info("hashrate_1m", gerty)
        data = r
        stat["current"] = data["currentHashrate"]
        stat["1w"] = data["hashrates"][len(data["hashrates"]) - 7]["avgHashrate"]
    elif stat_slug == "mining_current_difficulty":
        r = await get_mempool_info("hashrate_1m", gerty)
        data = r
        stat["current"] = data["currentDifficulty"]
        stat["previous"] = data["difficulty"][len(data["difficulty"]) - 2]["difficulty"]
    return stat


###########################################


async def get_satoshi():
    maxQuoteLength = 186
    with open(
        os.path.join(settings.lnbits_path, "extensions/gerty/static/satoshi.json")
    ) as fd:
        satoshiQuotes = json.load(fd)
    quote = satoshiQuotes[random.randint(0, len(satoshiQuotes) - 1)]
    # logger.debug(quote.text)
    if len(quote["text"]) > maxQuoteLength:
        logger.trace("Quote is too long, getting another")
        return await get_satoshi()
    else:
        return quote


# Get a screen slug by its position in the screens_list
def get_screen_slug_by_index(index: int, screens_list):
    if index <= len(screens_list) - 1:
        return list(screens_list)[index - 1]
    else:
        return None


# Get a list of text items for the screen number
async def get_screen_data(screen_num: int, screens_list: list, gerty):
    screen_slug = get_screen_slug_by_index(screen_num, screens_list)
    # first get the relevant slug from the display_preferences
    areas: List = []
    title = ""

    if screen_slug == "dashboard":
        title = gerty.name
        areas = await get_dashboard(gerty)

    if screen_slug == "lnbits_wallets_balance":
        wallets = await get_lnbits_wallet_balances(gerty)

        for wallet in wallets:
            text = []
            text.append(
                get_text_item_dict(
                    text="{0}'s Wallet".format(wallet["name"]),
                    font_size=20,
                    gerty_type=gerty.type,
                )
            )
            text.append(
                get_text_item_dict(
                    text="{0} sats".format(format_number(wallet["balance"])),
                    font_size=40,
                    gerty_type=gerty.type,
                )
            )
            areas.append(text)
    elif screen_slug == "url_checker":
        for url in json.loads(gerty.urls):
            async with httpx.AsyncClient() as client:
                text = []
                try:
                    response = await client.get(url)
                    text.append(
                        get_text_item_dict(
                            text=make_url_readable(url),
                            font_size=20,
                            gerty_type=gerty.type,
                        )
                    )
                    text.append(
                        get_text_item_dict(
                            text=str(response.status_code),
                            font_size=40,
                            gerty_type=gerty.type,
                        )
                    )
                except:
                    text = []
                    text.append(
                        get_text_item_dict(
                            text=make_url_readable(url),
                            font_size=20,
                            gerty_type=gerty.type,
                        )
                    )
                    text.append(
                        get_text_item_dict(
                            text=str("DOWN"),
                            font_size=40,
                            gerty_type=gerty.type,
                        )
                    )
                areas.append(text)
    elif screen_slug == "fun_satoshi_quotes":
        areas.append(await get_satoshi_quotes(gerty))
    elif screen_slug == "fun_exchange_market_rate":
        areas.append(await get_exchange_rate(gerty))
    elif screen_slug == "onchain_difficulty_epoch_progress":
        areas.append(await get_onchain_stat(screen_slug, gerty))
    elif screen_slug == "onchain_block_height":
        text = []
        text.append(
            get_text_item_dict(
                text="Block Height",
                font_size=20,
                gerty_type=gerty.type,
            )
        )
        text.append(
            get_text_item_dict(
                text=format_number(await get_mempool_info("tip_height", gerty)),
                font_size=80,
                gerty_type=gerty.type,
            )
        )
        areas.append(text)
    elif screen_slug == "onchain_difficulty_retarget_date":
        areas.append(await get_onchain_stat(screen_slug, gerty))
    elif screen_slug == "onchain_difficulty_blocks_remaining":
        areas.append(await get_onchain_stat(screen_slug, gerty))
    elif screen_slug == "onchain_difficulty_epoch_time_remaining":
        areas.append(await get_onchain_stat(screen_slug, gerty))
    elif screen_slug == "dashboard_onchain":
        title = "Onchain Data"
        areas = await get_onchain_dashboard(gerty)
    elif screen_slug == "mempool_recommended_fees":
        areas.append(await get_mempool_stat(screen_slug, gerty))
    elif screen_slug == "mempool_tx_count":
        areas.append(await get_mempool_stat(screen_slug, gerty))
    elif screen_slug == "mining_current_hash_rate":
        areas.append(await get_mining_stat(screen_slug, gerty))
    elif screen_slug == "mining_current_difficulty":
        areas.append(await get_mining_stat(screen_slug, gerty))
    elif screen_slug == "dashboard_mining":
        title = "Mining Data"
        areas = await get_mining_dashboard(gerty)
    elif screen_slug == "lightning_dashboard":
        title = "Lightning Network"
        areas = await get_lightning_stats(gerty)

    data = {
        "title": title,
        "areas": areas,
    }
    return data


# Get the dashboard screen
async def get_dashboard(gerty):
    areas = []
    # XC rate
    text = []
    amount = await satoshis_amount_as_fiat(100000000, gerty.exchange)
    text.append(
        get_text_item_dict(
            text=format_number(amount), font_size=40, gerty_type=gerty.type
        )
    )
    text.append(
        get_text_item_dict(
            text="BTC{0} price".format(gerty.exchange),
            font_size=15,
            gerty_type=gerty.type,
        )
    )
    areas.append(text)
    # balance
    text = []
    wallets = await get_lnbits_wallet_balances(gerty)
    text = []
    for wallet in wallets:
        text.append(
            get_text_item_dict(
                text="{0}".format(wallet["name"]), font_size=15, gerty_type=gerty.type
            )
        )
        text.append(
            get_text_item_dict(
                text="{0} sats".format(format_number(wallet["balance"])),
                font_size=20,
                gerty_type=gerty.type,
            )
        )
    areas.append(text)

    # Mempool fees
    text = []
    text.append(
        get_text_item_dict(
            text=format_number(await get_mempool_info("tip_height", gerty)),
            font_size=40,
            gerty_type=gerty.type,
        )
    )
    text.append(
        get_text_item_dict(
            text="Current block height", font_size=15, gerty_type=gerty.type
        )
    )
    areas.append(text)

    # difficulty adjustment time
    text = []
    text.append(
        get_text_item_dict(
            text=await get_time_remaining_next_difficulty_adjustment(gerty) or "0",
            font_size=15,
            gerty_type=gerty.type,
        )
    )
    text.append(
        get_text_item_dict(
            text="until next difficulty adjustment", font_size=12, gerty_type=gerty.type
        )
    )
    areas.append(text)

    return areas


async def get_lnbits_wallet_balances(gerty):
    # Get Wallet info
    wallets = []
    if gerty.lnbits_wallets != "":
        for lnbits_wallet in json.loads(gerty.lnbits_wallets):
            wallet = await get_wallet_for_key(key=lnbits_wallet)
            if wallet:
                wallets.append(
                    {
                        "name": wallet.name,
                        "balance": wallet.balance_msat / 1000,
                        "inkey": wallet.inkey,
                    }
                )
    return wallets


async def get_placeholder_text(gerty):
    return [
        get_text_item_dict(
            text="Some placeholder text",
            x_pos=15,
            y_pos=10,
            font_size=50,
            gerty_type=gerty.type,
        ),
        get_text_item_dict(
            text="Some placeholder text",
            x_pos=15,
            y_pos=10,
            font_size=50,
            gerty_type=gerty.type,
        ),
    ]


async def get_satoshi_quotes(gerty):
    # Get Satoshi quotes
    text = []
    quote = await get_satoshi()
    if quote:
        if quote["text"]:
            text.append(
                get_text_item_dict(
                    text=quote["text"], font_size=15, gerty_type=gerty.type
                )
            )
        if quote["date"]:
            text.append(
                get_text_item_dict(
                    text="Satoshi Nakamoto - {0}".format(quote["date"]),
                    font_size=15,
                    gerty_type=gerty.type,
                )
            )
    return text


# Get Exchange Value
async def get_exchange_rate(gerty):
    text = []
    if gerty.exchange != "":
        try:
            amount = await satoshis_amount_as_fiat(100000000, gerty.exchange)
            if amount:
                price = format_number(amount)
                text.append(
                    get_text_item_dict(
                        text="Current {0}/BTC price".format(gerty.exchange),
                        font_size=15,
                        gerty_type=gerty.type,
                    )
                )
                text.append(
                    get_text_item_dict(text=price, font_size=80, gerty_type=gerty.type)
                )
        except:
            pass
    return text


async def get_onchain_stat(stat_slug: str, gerty):
    text = []
    if (
        stat_slug == "onchain_difficulty_epoch_progress"
        or stat_slug == "onchain_difficulty_retarget_date"
        or stat_slug == "onchain_difficulty_blocks_remaining"
        or stat_slug == "onchain_difficulty_epoch_time_remaining"
    ):
        r = await get_mempool_info("difficulty_adjustment", gerty)
        if stat_slug == "onchain_difficulty_epoch_progress":
            stat = round(r["progressPercent"])
            text.append(
                get_text_item_dict(
                    text="Progress through current difficulty epoch",
                    font_size=15,
                    gerty_type=gerty.type,
                )
            )
            text.append(
                get_text_item_dict(
                    text="{0}%".format(stat), font_size=80, gerty_type=gerty.type
                )
            )
        elif stat_slug == "onchain_difficulty_retarget_date":
            stat = r["estimatedRetargetDate"]
            dt = datetime.fromtimestamp(stat / 1000).strftime("%e %b %Y at %H:%M")
            text.append(
                get_text_item_dict(
                    text="Date of next difficulty adjustment",
                    font_size=15,
                    gerty_type=gerty.type,
                )
            )
            text.append(
                get_text_item_dict(text=dt, font_size=40, gerty_type=gerty.type)
            )
        elif stat_slug == "onchain_difficulty_blocks_remaining":
            stat = r["remainingBlocks"]
            text.append(
                get_text_item_dict(
                    text="Blocks until next difficulty adjustment",
                    font_size=15,
                    gerty_type=gerty.type,
                )
            )
            text.append(
                get_text_item_dict(
                    text="{0}".format(format_number(stat)),
                    font_size=80,
                    gerty_type=gerty.type,
                )
            )
        elif stat_slug == "onchain_difficulty_epoch_time_remaining":
            stat = r["remainingTime"]
            text.append(
                get_text_item_dict(
                    text="Time until next difficulty adjustment",
                    font_size=15,
                    gerty_type=gerty.type,
                )
            )
            text.append(
                get_text_item_dict(
                    text=get_time_remaining(stat / 1000, 4),
                    font_size=20,
                    gerty_type=gerty.type,
                )
            )
    return text


async def get_onchain_dashboard(gerty):
    areas = []
    if isinstance(gerty.mempool_endpoint, str):
        text = []
        stat = (format_number(await get_mempool_info("tip_height", gerty)),)
        text.append(
            get_text_item_dict(
                text="Current block height", font_size=12, gerty_type=gerty.type
            )
        )
        text.append(
            get_text_item_dict(text=stat[0], font_size=40, gerty_type=gerty.type)
        )
        areas.append(text)

        r = await get_mempool_info("difficulty_adjustment", gerty)
        text = []
        stat = round(r["progressPercent"])
        text.append(
            get_text_item_dict(
                text="Progress through current epoch",
                font_size=12,
                gerty_type=gerty.type,
            )
        )
        text.append(
            get_text_item_dict(
                text="{0}%".format(stat), font_size=40, gerty_type=gerty.type
            )
        )
        areas.append(text)

        text = []
        stat = r["estimatedRetargetDate"]
        dt = datetime.fromtimestamp(stat / 1000).strftime("%e %b %Y at %H:%M")
        text.append(
            get_text_item_dict(
                text="Date of next adjustment", font_size=12, gerty_type=gerty.type
            )
        )
        text.append(get_text_item_dict(text=dt, font_size=20, gerty_type=gerty.type))
        areas.append(text)

        text = []
        stat = r["remainingBlocks"]
        text.append(
            get_text_item_dict(
                text="Blocks until adjustment", font_size=12, gerty_type=gerty.type
            )
        )
        text.append(
            get_text_item_dict(
                text="{0}".format(format_number(stat)),
                font_size=40,
                gerty_type=gerty.type,
            )
        )
        areas.append(text)

    return areas


async def get_time_remaining_next_difficulty_adjustment(gerty):
    if isinstance(gerty.mempool_endpoint, str):
        r = await get_mempool_info("difficulty_adjustment", gerty)
        stat = r["remainingTime"]
        time = get_time_remaining(stat / 1000, 3)
        return time


async def get_mempool_stat(stat_slug: str, gerty):
    text = []
    if isinstance(gerty.mempool_endpoint, str):
        if stat_slug == "mempool_tx_count":
            r = await get_mempool_info("mempool", gerty)
            if stat_slug == "mempool_tx_count":
                stat = round(r["count"])
                text.append(
                    get_text_item_dict(
                        text="Transactions in the mempool",
                        font_size=15,
                        gerty_type=gerty.type,
                    )
                )
                text.append(
                    get_text_item_dict(
                        text="{0}".format(format_number(stat)),
                        font_size=80,
                        gerty_type=gerty.type,
                    )
                )
        elif stat_slug == "mempool_recommended_fees":
            y_offset = 60
            fees = await get_mempool_info("fees_recommended", gerty)
            pos_y = 80 + y_offset
            text.append(get_text_item_dict("mempool.space", 40, 160, pos_y, gerty.type))
            pos_y = 180 + y_offset
            text.append(
                get_text_item_dict("Recommended Tx Fees", 20, 240, pos_y, gerty.type)
            )

            pos_y = 280 + y_offset
            text.append(
                get_text_item_dict("{0}".format("None"), 15, 30, pos_y, gerty.type)
            )
            text.append(
                get_text_item_dict("{0}".format("Low"), 15, 235, pos_y, gerty.type)
            )
            text.append(
                get_text_item_dict("{0}".format("Medium"), 15, 460, pos_y, gerty.type)
            )
            text.append(
                get_text_item_dict("{0}".format("High"), 15, 750, pos_y, gerty.type)
            )

            pos_y = 340 + y_offset
            font_size = 15
            fee_append = "/vB"
            fee_rate = fees["economyFee"]
            text.append(
                get_text_item_dict(
                    text="{0} {1}{2}".format(
                        format_number(fee_rate),
                        ("sat" if fee_rate == 1 else "sats"),
                        fee_append,
                    ),
                    font_size=font_size,
                    x_pos=30,
                    y_pos=pos_y,
                    gerty_type=gerty.type,
                )
            )

            fee_rate = fees["hourFee"]
            text.append(
                get_text_item_dict(
                    text="{0} {1}{2}".format(
                        format_number(fee_rate),
                        ("sat" if fee_rate == 1 else "sats"),
                        fee_append,
                    ),
                    font_size=font_size,
                    x_pos=235,
                    y_pos=pos_y,
                    gerty_type=gerty.type,
                )
            )

            fee_rate = fees["halfHourFee"]
            text.append(
                get_text_item_dict(
                    text="{0} {1}{2}".format(
                        format_number(fee_rate),
                        ("sat" if fee_rate == 1 else "sats"),
                        fee_append,
                    ),
                    font_size=font_size,
                    x_pos=460,
                    y_pos=pos_y,
                    gerty_type=gerty.type,
                )
            )

            fee_rate = fees["fastestFee"]
            text.append(
                get_text_item_dict(
                    text="{0} {1}{2}".format(
                        format_number(fee_rate),
                        ("sat" if fee_rate == 1 else "sats"),
                        fee_append,
                    ),
                    font_size=font_size,
                    x_pos=750,
                    y_pos=pos_y,
                    gerty_type=gerty.type,
                )
            )
    return text


def make_url_readable(url: str):
    return url.replace("https://", "").replace("http://", "").strip("/")
