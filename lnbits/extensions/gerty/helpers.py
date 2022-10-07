import datetime
import pytz
import httpx
import textwrap
from loguru import logger

from .number_prefixer import *

def get_percent_difference(current, previous, precision=4):
    difference = (current - previous) / current * 100
    return "{0}{1}%".format("+" if difference > 0 else "", round(difference, precision))

# A helper function get a nicely formated dict for the text
def get_text_item_dict(text: str, font_size: int, x_pos: int = None, y_pos: int = None):
    # Get line size by font size
    line_width = 60
    if font_size <= 12:
        line_width = 75
    elif font_size <= 15:
        line_width = 58
    elif font_size <= 20:
        line_width = 40
    elif font_size <= 40:
        line_width = 30
    else:
        line_width = 20

    #  wrap the text
    wrapper = textwrap.TextWrapper(width=line_width)
    word_list = wrapper.wrap(text=text)
    # logger.debug("number of chars = {0}".format(len(text)))

    multilineText = '\n'.join(word_list)
    # logger.debug("number of lines = {0}".format(len(word_list)))

    # logger.debug('multilineText')
    # logger.debug(multilineText)

    text = {
        "value": multilineText,
        "size": font_size
    }
    if x_pos is None and y_pos is None:
        text['position'] = 'center'
    else:
        text['x'] = x_pos
        text['y'] = y_pos
    return text

# format a number for nice display output
def format_number(number, precision=None):
    return ("{:,}".format(round(number, precision)))


async def get_mempool_recommended_fees(gerty):
    if isinstance(gerty.mempool_endpoint, str):
        async with httpx.AsyncClient() as client:
            r = await client.get(gerty.mempool_endpoint + "/api/v1/fees/recommended")
    return r.json()

async def api_get_mining_stat(stat_slug: str, gerty):
    stat = "";
    if isinstance(gerty.mempool_endpoint, str):
        async with httpx.AsyncClient() as client:
            if stat_slug == "mining_current_hash_rate":
                r = await client.get(gerty.mempool_endpoint + "/api/v1/mining/hashrate/1m")
                data = r.json()
                stat = {}
                stat['current'] = data['currentHashrate']
                stat['1w'] = data['hashrates'][len(data['hashrates']) - 7]['avgHashrate']
            elif stat_slug == "mining_current_difficulty":
                r = await client.get(gerty.mempool_endpoint + "/api/v1/mining/hashrate/1m")
                data = r.json()
                stat = {}
                stat['current'] = data['currentDifficulty']
                stat['previous'] = data['difficulty'][len(data['difficulty']) - 2]['difficulty']
    return stat

async def api_get_lightning_stats(gerty):
    stat = {}
    if isinstance(gerty.mempool_endpoint, str):
        async with httpx.AsyncClient() as client:
            r = await client.get(gerty.mempool_endpoint + "/api/v1/lightning/statistics/latest")
            data = r.json()
    return data

async def get_lightning_stats(gerty):
    data = await api_get_lightning_stats(gerty)
    areas = []

    logger.debug(data['latest']['channel_count'])

    text = []
    text.append(get_text_item_dict("Channel Count", 12))
    text.append(get_text_item_dict(format_number(data['latest']['channel_count']), 20))
    difference = get_percent_difference(current=data['latest']['channel_count'],
                                        previous=data['previous']['channel_count'])
    text.append(get_text_item_dict("{0} in last 7 days".format(difference), 12))
    areas.append(text)

    text = []
    text.append(get_text_item_dict("Number of Nodes", 12))
    text.append(get_text_item_dict(format_number(data['latest']['node_count']), 20))
    difference = get_percent_difference(current=data['latest']['node_count'], previous=data['previous']['node_count'])
    text.append(get_text_item_dict("{0} in last 7 days".format(difference), 12))
    areas.append(text)

    text = []
    text.append(get_text_item_dict("Total Capacity", 12))
    avg_capacity = float(data['latest']['total_capacity']) / float(100000000)
    text.append(get_text_item_dict("{0} BTC".format(format_number(avg_capacity, 2)), 20))
    difference = get_percent_difference(current=data['latest']['total_capacity'], previous=data['previous']['total_capacity'])
    text.append(get_text_item_dict("{0} in last 7 days".format(difference), 12))
    areas.append(text)

    text = []
    text.append(get_text_item_dict("Average Channel Capacity", 12))
    text.append(get_text_item_dict("{0} sats".format(format_number(data['latest']['avg_capacity'])), 20))
    difference = get_percent_difference(current=data['latest']['avg_capacity'], previous=data['previous']['avg_capacity'])
    text.append(get_text_item_dict("{0} in last 7 days".format(difference), 12))
    areas.append(text)

    return areas

async def get_mining_stat(stat_slug: str, gerty):
    text = []
    if stat_slug == "mining_current_hash_rate":
        stat = await api_get_mining_stat(stat_slug, gerty)
        logger.debug(stat)
        current = "{0}hash".format(si_format(stat['current'], 6, True, " "))
        text.append(get_text_item_dict("Current Mining Hashrate", 20))
        text.append(get_text_item_dict(current, 40))
        # compare vs previous time period
        difference = get_percent_difference(current=stat['current'], previous=stat['1w'])
        text.append(get_text_item_dict("{0} in last 7 days".format(difference), 12))
    elif stat_slug == "mining_current_difficulty":
        stat = await api_get_mining_stat(stat_slug, gerty)
        text.append(get_text_item_dict("Current Mining Difficulty", 20))
        text.append(get_text_item_dict(format_number(stat['current']), 40))
        difference = get_percent_difference(current=stat['current'], previous=stat['previous'])
        text.append(get_text_item_dict("{0} since last adjustment".format(difference), 12))
        # text.append(get_text_item_dict("Required threshold for mining proof-of-work", 12))
    return text

def get_next_update_time(sleep_time_seconds: int = 0, timezone: str = "Europe/London"):
    utc_now = pytz.utc.localize(datetime.datetime.utcnow())
    next_refresh_time = utc_now + datetime.timedelta(0, sleep_time_seconds)
    local_refresh_time = next_refresh_time.astimezone(pytz.timezone(timezone))
    return "{0} {1}".format("I'll wake up at" if gerty_should_sleep() else "Next update at",local_refresh_time.strftime("%H:%M on%e %b %Y"))

def gerty_should_sleep(timezone: str = "Europe/London"):
    utc_now = pytz.utc.localize(datetime.datetime.utcnow())
    local_time = utc_now.astimezone(pytz.timezone(timezone))
    hours = local_time.strftime("%H")
    hours = int(hours)
    logger.debug("HOURS")
    logger.debug(hours)
    if(hours >= 22 and hours <= 23):
        return True
    else:
        return False
