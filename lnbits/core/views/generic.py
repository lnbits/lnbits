import asyncio
from http import HTTPStatus
from typing import Optional

from fastapi import Request, status
from fastapi.exceptions import HTTPException
from fastapi.params import Depends, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.routing import APIRouter
from pydantic.types import UUID4
from starlette.responses import HTMLResponse, JSONResponse

from lnbits.core import db
from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.helpers import template_renderer, url_for
from lnbits.settings import (
    LNBITS_ADMIN_USERS,
    LNBITS_ALLOWED_USERS,
    LNBITS_CUSTOM_LOGO,
    LNBITS_SITE_TITLE,
    SERVICE_FEE,
)

from ..crud import (
    create_account,
    create_wallet,
    delete_wallet,
    get_balance_check,
    get_user,
    save_balance_notify,
    update_user_extension,
)
from ..services import pay_invoice, redeem_lnurl_withdraw

core_html_routes: APIRouter = APIRouter(tags=["Core NON-API Website Routes"])


@core_html_routes.get("/favicon.ico", response_class=FileResponse)
async def favicon():
    return FileResponse("lnbits/core/static/favicon.ico")


@core_html_routes.get("/", response_class=HTMLResponse)
async def home(request: Request, lightning: str = None):
    return template_renderer().TemplateResponse(
        "core/index.html", {"request": request, "lnurl": lightning}
    )


@core_html_routes.get(
    "/extensions", name="core.extensions", response_class=HTMLResponse
)
async def extensions(
    request: Request,
    user: User = Depends(check_user_exists),
    enable: str = Query(None),
    disable: str = Query(None),
):
    extension_to_enable = enable
    extension_to_disable = disable

    if extension_to_enable and extension_to_disable:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "You can either `enable` or `disable` an extension."
        )

    if extension_to_enable:
        await update_user_extension(
            user_id=user.id, extension=extension_to_enable, active=True
        )
    elif extension_to_disable:
        await update_user_extension(
            user_id=user.id, extension=extension_to_disable, active=False
        )

    # Update user as his extensions have been updated
    if extension_to_enable or extension_to_disable:
        user = await get_user(user.id)

    return template_renderer().TemplateResponse(
        "core/extensions.html", {"request": request, "user": user.dict()}
    )


@core_html_routes.get(
    "/wallet",
    response_class=HTMLResponse,
    description="""
Args:

just **wallet_name**: create a new user, then create a new wallet for user with wallet_name<br>
just **user_id**: return the first user wallet or create one if none found (with default wallet_name)<br>
**user_id** and **wallet_name**: create a new wallet for user with wallet_name<br>
**user_id** and **wallet_id**: return that wallet if user is the owner<br>
nothing: create everything<br>
""",
)
async def wallet(
    request: Request = Query(None),
    nme: Optional[str] = Query(None),
    usr: Optional[UUID4] = Query(None),
    wal: Optional[UUID4] = Query(None),
):
    user_id = usr.hex if usr else None
    wallet_id = wal.hex if wal else None
    wallet_name = nme
    service_fee = int(SERVICE_FEE) if int(SERVICE_FEE) == SERVICE_FEE else SERVICE_FEE

    if not user_id:
        user = await get_user((await create_account()).id)
    else:
        user = await get_user(user_id)
        if not user:
            return template_renderer().TemplateResponse(
                "error.html", {"request": request, "err": "User does not exist."}
            )
        if LNBITS_ALLOWED_USERS and user_id not in LNBITS_ALLOWED_USERS:
            return template_renderer().TemplateResponse(
                "error.html", {"request": request, "err": "User not authorized."}
            )
        if LNBITS_ADMIN_USERS and user_id in LNBITS_ADMIN_USERS:
            user.admin = True
    if not wallet_id:
        if user.wallets and not wallet_name:
            wallet = user.wallets[0]
        else:
            wallet = await create_wallet(user_id=user.id, wallet_name=wallet_name)

        return RedirectResponse(
            f"/wallet?usr={user.id}&wal={wallet.id}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    wallet = user.get_wallet(wallet_id)
    if not wallet:
        return template_renderer().TemplateResponse(
            "error.html", {"request": request, "err": "Wallet not found"}
        )

    return template_renderer().TemplateResponse(
        "core/wallet.html",
        {
            "request": request,
            "user": user.dict(),
            "wallet": wallet.dict(),
            "service_fee": service_fee,
        },
    )


@core_html_routes.get("/withdraw", response_class=JSONResponse)
async def lnurl_full_withdraw(request: Request):
    user = await get_user(request.query_params.get("usr"))
    if not user:
        return {"status": "ERROR", "reason": "User does not exist."}

    wallet = user.get_wallet(request.query_params.get("wal"))
    if not wallet:
        return {"status": "ERROR", "reason": "Wallet does not exist."}

    return {
        "tag": "withdrawRequest",
        "callback": url_for("/withdraw/cb", external=True, usr=user.id, wal=wallet.id),
        "k1": "0",
        "minWithdrawable": 1000 if wallet.withdrawable_balance else 0,
        "maxWithdrawable": wallet.withdrawable_balance,
        "defaultDescription": f"{LNBITS_SITE_TITLE} balance withdraw from {wallet.id[0:5]}",
        "balanceCheck": url_for("/withdraw", external=True, usr=user.id, wal=wallet.id),
    }


@core_html_routes.get("/withdraw/cb", response_class=JSONResponse)
async def lnurl_full_withdraw_callback(request: Request):
    user = await get_user(request.query_params.get("usr"))
    if not user:
        return {"status": "ERROR", "reason": "User does not exist."}

    wallet = user.get_wallet(request.query_params.get("wal"))
    if not wallet:
        return {"status": "ERROR", "reason": "Wallet does not exist."}

    pr = request.query_params.get("pr")

    async def pay():
        try:
            await pay_invoice(wallet_id=wallet.id, payment_request=pr)
        except:
            pass

    asyncio.create_task(pay())

    balance_notify = request.query_params.get("balanceNotify")
    if balance_notify:
        await save_balance_notify(wallet.id, balance_notify)

    return {"status": "OK"}


@core_html_routes.get("/deletewallet", response_class=RedirectResponse)
async def deletewallet(request: Request, wal: str = Query(...), usr: str = Query(...)):
    user = await get_user(usr)
    user_wallet_ids = [u.id for u in user.wallets]
    print("USR", user_wallet_ids)

    if wal not in user_wallet_ids:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not your wallet.")
    else:
        await delete_wallet(user_id=user.id, wallet_id=wal)
        user_wallet_ids.remove(wal)

    if user_wallet_ids:
        return RedirectResponse(
            url_for("/wallet", usr=user.id, wal=user_wallet_ids[0]),
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    return RedirectResponse(
        url_for("/"), status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@core_html_routes.get("/withdraw/notify/{service}")
async def lnurl_balance_notify(request: Request, service: str):
    bc = await get_balance_check(request.query_params.get("wal"), service)
    if bc:
        redeem_lnurl_withdraw(bc.wallet, bc.url)


@core_html_routes.get(
    "/lnurlwallet", response_class=RedirectResponse, name="core.lnurlwallet"
)
async def lnurlwallet(request: Request):
    async with db.connect() as conn:
        account = await create_account(conn=conn)
        user = await get_user(account.id, conn=conn)
        wallet = await create_wallet(user_id=user.id, conn=conn)

    asyncio.create_task(
        redeem_lnurl_withdraw(
            wallet.id,
            request.query_params.get("lightning"),
            "LNbits initial funding: voucher redeem.",
            {"tag": "lnurlwallet"},
            5,  # wait 5 seconds before sending the invoice to the service
        )
    )

    return RedirectResponse(
        f"/wallet?usr={user.id}&wal={wallet.id}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@core_html_routes.get("/service-worker.js", response_class=FileResponse)
async def service_worker():
    return FileResponse("lnbits/core/static/js/service-worker.js")


@core_html_routes.get("/manifest/{usr}.webmanifest")
async def manifest(usr: str):
    user = await get_user(usr)
    if not user:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    return {
        "short_name": LNBITS_SITE_TITLE,
        "name": LNBITS_SITE_TITLE + " Wallet",
        "icons": [
            {
                "src": LNBITS_CUSTOM_LOGO
                if LNBITS_CUSTOM_LOGO
                else "https://cdn.jsdelivr.net/gh/lnbits/lnbits@0.3.0/docs/logos/lnbits.png",
                "type": "image/png",
                "sizes": "900x900",
            }
        ],
        "start_url": "/wallet?usr=" + usr + "&wal=" + user.wallets[0].id,
        "background_color": "#1F2234",
        "description": "Bitcoin Lightning Wallet",
        "display": "standalone",
        "scope": "/",
        "theme_color": "#1F2234",
        "shortcuts": [
            {
                "name": wallet.name,
                "short_name": wallet.name,
                "description": wallet.name,
                "url": "/wallet?usr=" + usr + "&wal=" + wallet.id,
            }
            for wallet in user.wallets
        ],
    }
