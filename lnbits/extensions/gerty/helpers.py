import httpx
import textwrap
from loguru import logger

from .number_prefixer import *


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
def format_number(number):
    return ("{:,}".format(round(number)))


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


async def get_mining_stat(stat_slug: str, gerty):
    text = []
    if stat_slug == "mining_current_hash_rate":
        stat = await api_get_mining_stat(stat_slug, gerty)
        logger.debug(stat)
        current = "{0}hash".format(si_format(stat['current'], 6, True, " "))
        text.append(get_text_item_dict("Current Mining Hashrate", 20))
        text.append(get_text_item_dict(current, 40))
        # compare vs previous time period
        difference = (stat['current'] - stat['1w']) / stat['current'] * 100
        text.append(get_text_item_dict("{0}{1}% in last 7 days".format("+" if difference > 0 else "", round(difference, 4)), 12))
    elif stat_slug == "mining_current_difficulty":
        stat = await api_get_mining_stat(stat_slug, gerty)
        text.append(get_text_item_dict("Current Mining Difficulty", 20))
        text.append(get_text_item_dict(format_number(stat['current']), 40))
        difference = (stat['current'] - stat['previous']) / stat['current'] * 100
        text.append(
            get_text_item_dict("{0}{1}% since last adjustment".format("+" if difference > 0 else "", round(difference, 4)),
                               15))
        # text.append(get_text_item_dict("Required threshold for mining proof-of-work", 12))
    return text