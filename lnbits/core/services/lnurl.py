import asyncio
from typing import Optional
from urllib.parse import urlparse

import httpx
from loguru import logger

from lnbits.db import Connection
from lnbits.helpers import check_callback_url, url_for
from lnbits.lnurl import decode as decode_lnurl
from lnbits.settings import settings

from .payments import create_invoice


async def redeem_lnurl_withdraw(
    wallet_id: str,
    lnurl_request: str,
    memo: Optional[str] = None,
    extra: Optional[dict] = None,
    wait_seconds: int = 0,
    conn: Optional[Connection] = None,
) -> None:
    if not lnurl_request:
        return None

    res = {}

    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(headers=headers) as client:
        lnurl = decode_lnurl(lnurl_request)
        check_callback_url(str(lnurl))
        r = await client.get(str(lnurl))
        res = r.json()

    try:
        _, payment_request = await create_invoice(
            wallet_id=wallet_id,
            amount=int(res["maxWithdrawable"] / 1000),
            memo=memo or res["defaultDescription"] or "",
            extra=extra,
            conn=conn,
        )
    except Exception:
        logger.warning(
            f"failed to create invoice on redeem_lnurl_withdraw "
            f"from {lnurl}. params: {res}"
        )
        return None

    if wait_seconds:
        await asyncio.sleep(wait_seconds)

    params = {"k1": res["k1"], "pr": payment_request}

    try:
        params["balanceNotify"] = url_for(
            f"/withdraw/notify/{urlparse(lnurl_request).netloc}",
            external=True,
            wal=wallet_id,
        )
    except Exception:
        pass

    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            check_callback_url(res["callback"])
            await client.get(res["callback"], params=params)
        except Exception:
            pass
