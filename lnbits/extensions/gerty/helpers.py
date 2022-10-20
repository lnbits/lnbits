from datetime import datetime, timedelta
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

async def get_mining_dashboard(gerty):
    areas = []
    if isinstance(gerty.mempool_endpoint, str):
        async with httpx.AsyncClient() as client:
            # current hashrate
            r = await client.get(gerty.mempool_endpoint + "/api/v1/mining/hashrate/1w")
            data = r.json()
            hashrateNow = data['currentHashrate']
            hashrateOneWeekAgo = data['hashrates'][6]['avgHashrate']

            text = []
            text.append(get_text_item_dict("Current mining hashrate", 12))
            text.append(get_text_item_dict("{0}hash".format(si_format(hashrateNow, 6, True, " ")), 20))
            text.append(get_text_item_dict("{0} vs 7 days ago".format(get_percent_difference(hashrateNow, hashrateOneWeekAgo, 3)), 12))
            areas.append(text)

            r = await client.get(gerty.mempool_endpoint + "/api/v1/difficulty-adjustment")

            # timeAvg
            text = []
            progress = "{0}%".format(round(r.json()['progressPercent'], 2))
            text.append(get_text_item_dict("Progress through current epoch", 12))
            text.append(get_text_item_dict(progress, 20))
            areas.append(text)

            # difficulty adjustment
            text = []
            stat = r.json()['remainingTime']
            text.append(get_text_item_dict("Time to next difficulty adjustment", 12))
            text.append(get_text_item_dict(get_time_remaining(stat / 1000, 3), 20))
            areas.append(text)

            # difficultyChange
            text = []
            difficultyChange = round(r.json()['difficultyChange'], 2)
            text.append(get_text_item_dict("Estimated difficulty change", 12))
            text.append(get_text_item_dict("{0}{1}%".format("+" if difficultyChange > 0 else "", round(difficultyChange, 2)), 20))
            areas.append(text)

            r = await client.get(gerty.mempool_endpoint + "/api/v1/mining/hashrate/1m")
            data = r.json()
            stat = {}
            stat['current'] = data['currentDifficulty']
            stat['previous'] = data['difficulty'][len(data['difficulty']) - 2]['difficulty']
    return areas

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

def get_next_update_time(sleep_time_seconds: int = 0, timezone: str = "Europe/London"):
    utc_now = pytz.utc.localize(datetime.utcnow())
    next_refresh_time = utc_now + timedelta(0, sleep_time_seconds)
    local_refresh_time = next_refresh_time.astimezone(pytz.timezone(timezone))
    return "{0} {1}".format("I'll wake up at" if gerty_should_sleep() else "Next update at",local_refresh_time.strftime("%H:%M on %e %b %Y"))

def gerty_should_sleep(timezone: str = "Europe/London"):
    utc_now = pytz.utc.localize(datetime.utcnow())
    local_time = utc_now.astimezone(pytz.timezone(timezone))
    hours = local_time.strftime("%H")
    hours = int(hours)
    logger.debug("HOURS")
    logger.debug(hours)
    if(hours >= 22 and hours <= 23):
        return True
    else:
        return False



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
