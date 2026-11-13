from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.routing import APIRouter
from lnurl import LnurlException, LnurlWithdrawResponse, url_decode

from lnbits.core.helpers import to_valid_user_id
from lnbits.core.models import User
from lnbits.core.services import create_invoice, create_user_account
from lnbits.core.services.lnurl import execute_withdraw, handle
from lnbits.decorators import (
    check_admin,
    check_admin_ui,
    check_blockexplorer_access,
    check_blockexplorer_public,
    check_first_install,
    check_user_exists,
)
from lnbits.helpers import check_callback_url, template_renderer
from lnbits.settings import settings
from lnbits.utils.outbound import outbound_protection_status

generic_router = APIRouter(
    tags=["Core NON-API Website Routes"], include_in_schema=False
)


@generic_router.get("/favicon.ico", response_class=FileResponse)
async def favicon():
    return RedirectResponse(settings.lnbits_qr_logo)


@generic_router.get("/robots.txt", response_class=HTMLResponse)
async def robots():
    data = "User-agent: *\nDisallow: /"
    return HTMLResponse(content=data, media_type="text/plain")


@generic_router.get("/service-worker.js")
async def service_worker(request: Request):
    return template_renderer().TemplateResponse(
        request,
        "service-worker.js",
        {
            "cache_version": settings.server_startup_time,
        },
        media_type="text/javascript",
    )


admin_ui_checks = [Depends(check_admin), Depends(check_admin_ui)]


@generic_router.get("/payments")
@generic_router.get("/wallet")
@generic_router.get("/wallet/{wallet_id}")
@generic_router.get("/wallets")
@generic_router.get("/account")
@generic_router.get("/extensions")
@generic_router.get("/users", dependencies=admin_ui_checks)
@generic_router.get("/audit", dependencies=admin_ui_checks)
@generic_router.get("/scheduler", dependencies=admin_ui_checks)
@generic_router.get("/scheduler/runs", dependencies=admin_ui_checks)
@generic_router.get("/node", dependencies=admin_ui_checks)
@generic_router.get("/admin", dependencies=admin_ui_checks)
@generic_router.get("/admin/extensions/wasm", dependencies=admin_ui_checks)
@generic_router.get("/admin/extensions/wasm/limits", dependencies=admin_ui_checks)
@generic_router.get("/admin/extensions/wasm/{ext_id}", dependencies=admin_ui_checks)
async def index(
    request: Request,
    ext_id: str | None = None,
    user: User = Depends(check_user_exists),
) -> HTMLResponse:
    return template_renderer().TemplateResponse(
        request,
        "base.html",
        {
            "user": user.model_dump_json(),
            "outbound_protection": (
                outbound_protection_status() if user.super_user else None
            ),
        },
    )


@generic_router.get("/2fa")
async def two_factor_page(request: Request) -> HTMLResponse:
    return template_renderer().TemplateResponse(
        request,
        "two_factor.html",
        {"public": True},
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@generic_router.get("/")
@generic_router.get("/node/public")
@generic_router.get("/first_install", dependencies=[Depends(check_first_install)])
async def index_public(request: Request) -> HTMLResponse:
    return template_renderer().TemplateResponse(request, "base.html", {"public": True})


@generic_router.get("/blockexplorer")
@generic_router.get("/blockexplorer/{resource_type}/{resource}")
async def index_blockexplorer(
    request: Request,
    user: User = Depends(check_blockexplorer_access),
) -> HTMLResponse:
    return template_renderer().TemplateResponse(
        request, "base.html", {"user": user.model_dump_json()}
    )


@generic_router.get(
    "/blockexplorer/public", dependencies=[Depends(check_blockexplorer_public)]
)
@generic_router.get(
    "/blockexplorer/public/{resource_type}/{resource}",
    dependencies=[Depends(check_blockexplorer_public)],
)
async def index_blockexplorer_public(request: Request) -> HTMLResponse:
    return template_renderer().TemplateResponse(request, "base.html", {"public": True})


@generic_router.get("/uuidv4/{hex_value}")
async def hex_to_uuid4(hex_value: str):
    try:
        user_id = to_valid_user_id(hex_value).hex
        return RedirectResponse(url=f"/wallet?usr={user_id}")
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@generic_router.get("/lnurlwallet", response_class=RedirectResponse)
async def lnurlwallet(request: Request, lightning: str = ""):
    """
    If a user doesn't have a Lightning Network wallet and scans the LNURLw QR code with
    their smartphone camera, or a QR scanner app, they can follow the link provided to
    claim their satoshis and get an instant LNbits wallet! lnbits/withdraw docs
    """

    if not lightning:
        return {"status": "ERROR", "reason": "lightning parameter not provided."}
    if not settings.lnbits_allow_new_accounts:
        return {"status": "ERROR", "reason": "New accounts are not allowed."}

    try:
        lnurl = url_decode(lightning)
        check_callback_url(lnurl)
        withdraw = await handle(lnurl, user_agent=settings.user_agent, timeout=2)
        if not isinstance(withdraw, LnurlWithdrawResponse):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Invalid lnurl. Expected tag=withdrawRequest",
            )
        if not withdraw.maxWithdrawable:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Invalid lnurl. Expected maxWithdrawable",
            )
        check_callback_url(str(withdraw.callback))
    except (LnurlException, ValueError) as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc

    account = await create_user_account()
    wallet = account.wallets[0]
    payment = await create_invoice(
        wallet_id=wallet.id,
        amount=withdraw.maxWithdrawable / 1000,
        memo=withdraw.defaultDescription or "lnurl wallet withdraw",
    )

    try:
        await execute_withdraw(
            withdraw,
            payment.bolt11,
            user_agent=settings.user_agent,
            timeout=5,
        )
    except LnurlException as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc

    return RedirectResponse(
        f"/wallet?usr={account.id}&wal={wallet.id}",
    )
