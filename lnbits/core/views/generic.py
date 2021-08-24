from lnbits.core.models import Wallet
from fastapi.params import Query
from fastapi.routing import APIRouter
from fastapi.responses import RedirectResponse
from fastapi import status
from lnbits.requestvars import g
from os import path
from http import HTTPStatus
from typing import Optional
import jinja2

from starlette.responses import HTMLResponse

from lnbits.core import core_app, db
from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.settings import LNBITS_ALLOWED_USERS, SERVICE_FEE, LNBITS_SITE_TITLE

from ..crud import (
    create_account,
    get_user,
    update_user_extension,
    create_wallet,
    delete_wallet,
    get_balance_check,
    save_balance_notify,
)
from ..services import redeem_lnurl_withdraw, pay_invoice
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

core_html_routes: APIRouter = APIRouter(tags=["Core NON-API Website Routes"])

@core_html_routes.get("/favicon.ico")
async def favicon():
    return FileResponse("lnbits/core/static/favicon.ico")
    

@core_html_routes.get("/", response_class=HTMLResponse)
async def home(request: Request, lightning: str = None):
    return g().templates.TemplateResponse("core/index.html", {"request": request, "lnurl": lightning})


@core_html_routes.get("/extensions")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def extensions(enable: str, disable: str):
    extension_to_enable = enable
    extension_to_disable = disable

    if extension_to_enable and extension_to_disable:
        abort(
            HTTPStatus.BAD_REQUEST, "You can either `enable` or `disable` an extension."
        )

    if extension_to_enable:
        await update_user_extension(
            user_id=g.user.id, extension=extension_to_enable, active=True
        )
    elif extension_to_disable:
        await update_user_extension(
            user_id=g.user.id, extension=extension_to_disable, active=False
        )
    return await templates.TemplateResponse("core/extensions.html", {"request": request, "user": get_user(g.user.id)})


@core_html_routes.get("/wallet", response_class=HTMLResponse)
#Not sure how to validate
@validate_uuids(["usr", "wal"])
async def wallet(request: Request,
    usr: Optional[str] = Query(None),
    wal: Optional[str] = Query(None),
    nme: Optional[str] = Query(None),
    ):
                    
    user_id = usr
    wallet_id = wal
    wallet_name = nme
    service_fee = int(SERVICE_FEE) if int(SERVICE_FEE) == SERVICE_FEE else SERVICE_FEE

    # just wallet_name: create a new user, then create a new wallet for user with wallet_name
    # just user_id: return the first user wallet or create one if none found (with default wallet_name)
    # user_id and wallet_name: create a new wallet for user with wallet_name
    # user_id and wallet_id: return that wallet if user is the owner
    # nothing: create everything

    if not user_id:
        usr = await get_user((await create_account()).id)
    else:
        usr = await get_user(user_id)
        if not usr:
            return g().templates.TemplateResponse("error.html", {"request": request, "err": "User does not exist."})
        if LNBITS_ALLOWED_USERS and user_id not in LNBITS_ALLOWED_USERS:
            return g().templates.TemplateResponse("error.html", {"request": request, "err": "User not authorized."})
    if not wallet_id:
        if usr.wallets and not wallet_name:
            wal = usr.wallets[0]
        else:
            wal = await create_wallet(user_id=usr.id, wallet_name=wallet_name)

        return RedirectResponse(f"/wallet?usr={usr.id}&wal={wal.id}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    wal = usr.get_wallet(wallet_id)
    if not wal:
        return g().templates.TemplateResponse("error.html", {"request": request, ...})

    return g().templates.TemplateResponse(
        "core/wallet.html", {"request":request,"user":usr, "wallet":wal, "service_fee":service_fee}
    )


@core_html_routes.get("/withdraw")
@validate_uuids(["usr", "wal"], required=True)
async def lnurl_full_withdraw():
    user = await get_user(request.args.get("usr"))
    if not user:
        return {"status": "ERROR", "reason": "User does not exist."}

    wallet = user.get_wallet(request.args.get("wal"))
    if not wallet:
        return{"status": "ERROR", "reason": "Wallet does not exist."}

    return {
            "tag": "withdrawRequest",
            "callback": url_for(
                "core.lnurl_full_withdraw_callback",
                usr=user.id,
                wal=wallet.id,
                _external=True,
            ),
            "k1": "0",
            "minWithdrawable": 1000 if wallet.withdrawable_balance else 0,
            "maxWithdrawable": wallet.withdrawable_balance,
            "defaultDescription": f"{LNBITS_SITE_TITLE} balance withdraw from {wallet.id[0:5]}",
            "balanceCheck": url_for(
                "core.lnurl_full_withdraw", usr=user.id, wal=wallet.id, _external=True
            ),
        }


@core_html_routes.get("/withdraw/cb")
@validate_uuids(["usr", "wal"], required=True)
async def lnurl_full_withdraw_callback():
    user = await get_user(request.args.get("usr"))
    if not user:
        return {"status": "ERROR", "reason": "User does not exist."}

    wallet = user.get_wallet(request.args.get("wal"))
    if not wallet:
        return {"status": "ERROR", "reason": "Wallet does not exist."}

    pr = request.args.get("pr")

    async def pay():
        try:
            await pay_invoice(wallet_id=wallet.id, payment_request=pr)
        except:
            pass

    current_app.nursery.start_soon(pay)

    balance_notify = request.args.get("balanceNotify")
    if balance_notify:
        await save_balance_notify(wallet.id, balance_notify)

    return {"status": "OK"}


@core_html_routes.get("/deletewallet")
@validate_uuids(["usr", "wal"], required=True)
@check_user_exists()
async def deletewallet():
    wallet_id = request.args.get("wal", type=str)
    user_wallet_ids = g.user.wallet_ids

    if wallet_id not in user_wallet_ids:
        abort(HTTPStatus.FORBIDDEN, "Not your wallet.")
    else:
        await delete_wallet(user_id=g.user.id, wallet_id=wallet_id)
        user_wallet_ids.remove(wallet_id)

    if user_wallet_ids:
        return redirect(url_for("core.wallet", usr=g.user.id, wal=user_wallet_ids[0]))

    return redirect(url_for("core.home"))


@core_html_routes.get("/withdraw/notify/{service}")
@validate_uuids(["wal"], required=True)
async def lnurl_balance_notify(service: str):
    bc = await get_balance_check(request.args.get("wal"), service)
    if bc:
        redeem_lnurl_withdraw(bc.wallet, bc.url)


@core_html_routes.get("/lnurlwallet")
async def lnurlwallet():
    async with db.connect() as conn:
        account = await create_account(conn=conn)
        user = await get_user(account.id, conn=conn)
        wallet = await create_wallet(user_id=user.id, conn=conn)

    current_app.nursery.start_soon(
        redeem_lnurl_withdraw,
        wallet.id,
        request.args.get("lightning"),
        "LNbits initial funding: voucher redeem.",
        {"tag": "lnurlwallet"},
        5,  # wait 5 seconds before sending the invoice to the service
    )

    return redirect(url_for("core.wallet", usr=user.id, wal=wallet.id))


@core_html_routes.get("/manifest/{usr}.webmanifest")
async def manifest(usr: str):
    user = await get_user(usr)
    if not user:
        return "", HTTPStatus.NOT_FOUND

    return {
            "short_name": "LNbits",
            "name": "LNbits Wallet",
            "icons": [
                {
                    "src": "https://cdn.jsdelivr.net/gh/lnbits/lnbits@0.3.0/docs/logos/lnbits.png",
                    "type": "image/png",
                    "sizes": "900x900",
                }
            ],
            "start_url": "/wallet?usr=" + usr,
            "background_color": "#3367D6",
            "description": "Weather forecast information",
            "display": "standalone",
            "scope": "/",
            "theme_color": "#3367D6",
            "shortcuts": [
                {
                    "name": wallet.name,
                    "short_name": wallet.name,
                    "description": wallet.name,
                    "url": "/wallet?usr=" + usr + "&wal=" + wallet.id,
                }
                for wallet in user.wallets
            ],}
