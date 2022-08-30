import calendar
import datetime

import httpx
from loguru import logger

from lnbits.core.services import fee_reserve, get_wallet


async def check_balance(data) -> bool:
    # check if we can pay the invoice before we create the actual swap on boltz
    amount_msat = data.amount * 1000
    fee_reserve_msat = fee_reserve(amount_msat)
    wallet = await get_wallet(data.wallet)
    assert wallet
    if wallet.balance_msat - fee_reserve_msat < amount_msat:
        return False
    return True


def get_timestamp():
    date = datetime.datetime.utcnow()
    return calendar.timegm(date.utctimetuple())


def req_wrap(funcname, *args, **kwargs):
    try:
        try:
            func = getattr(httpx, funcname)
        except AttributeError:
            logger.error('httpx function not found "%s"' % funcname)
        else:
            res = func(*args, timeout=30, **kwargs)
        res.raise_for_status()
        return res
    except httpx.RequestError as exc:
        msg = f"Unreachable: {exc.request.url!r}."
        logger.error(msg)
        raise
    except httpx.HTTPStatusError as exc:
        msg = f"HTTP Status Error: {exc.response.status_code} while requesting {exc.request.url!r}."
        logger.error(msg)
        logger.error(exc.response.json()["error"])
        raise
