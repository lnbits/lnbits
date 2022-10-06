import httpx
import textwrap

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
                r = await client.get(gerty.mempool_endpoint + "/api/v1/mining/hashrate/3d")
                data = r.json()
                stat = data['currentHashrate']
    return stat


async def get_mining_stat(stat_slug: str, gerty):
    text = []
    if stat_slug == "mining_current_hash_rate":
        stat = await api_get_mining_stat(stat_slug, gerty)
        stat = "{0}hash".format(si_format(stat, 6, True, " "))
        text.append(get_text_item_dict("Current Hashrate", 20))
        text.append(get_text_item_dict(stat, 40))
    return text