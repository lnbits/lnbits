from http import HTTPStatus

import httpx
from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import hedge_ext, hedge_renderer
from .crud import get_hedge

templates = Jinja2Templates(directory="templates")


@hedge_ext.get("/")
async def index(request: Request, user: User = Depends(check_user_exists)):
    return hedge_renderer().TemplateResponse(
        "hedge/index.html", {"request": request, "user": user.dict()}
    )


@hedge_ext.get("/info/{hedge_id}")
async def tip(request: Request, hedge_id: int = Query(None)):
    """Return the donation form for the Tipjar corresponding to id"""
    hedge = await get_hedge(hedge_id)
    if not hedge:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Hedge does not exist."
        )

    stats = {
        "channels_sats": 0,
        "channels_usd": 0.0,
        "position_sats": 0,
        "position_usd": 0,
        "account_balance": 0.0,
    }

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                hedge.hedgeuri + "/stats",
                timeout=40,
            )
            stats = r.json()
        except Exception:
            pass

    return hedge_renderer().TemplateResponse(
        "hedge/stats.html",
        {
            "request": request,
            "ticker": hedge.ticker,
            "wallet": hedge.wallet,
            "host": hedge.hedgeuri,
            "stats": stats,
        },
    )
