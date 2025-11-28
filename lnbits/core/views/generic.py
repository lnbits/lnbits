from hashlib import sha256
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.routing import APIRouter
from lnurl import url_decode

from lnbits.core.helpers import to_valid_user_id
from lnbits.core.models import User
from lnbits.core.services import create_invoice, create_user_account
from lnbits.decorators import (
    check_admin,
    check_admin_ui,
    check_extension_builder,
    check_first_install,
    check_user_exists,
)
from lnbits.helpers import check_callback_url, template_renderer
from lnbits.settings import settings

from ..crud import get_user

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


@generic_router.get(
    "/extensions/builder/preview/{ext_id}",
    name="extensions builder",
    dependencies=[Depends(check_extension_builder)],
)
async def extensions_builder_preview(
    request: Request,
    ext_id: str,
    page_name: str | None = None,
    user: User = Depends(check_user_exists),
) -> HTMLResponse:
    working_dir_name = "preview_" + sha256(user.id.encode("utf-8")).hexdigest()
    html_file_name = "index.html"
    if page_name == "public_page":
        html_file_name = "public_page.html"

    html_file_path = Path(
        "extension_builder_stub",
        ext_id,
        working_dir_name,
        ext_id,
        "templates",
        ext_id,
        html_file_name,
    )

    html_file_full_path = Path(
        settings.extension_builder_working_dir_path, html_file_path
    )

    if not html_file_full_path.is_file():
        return template_renderer().TemplateResponse(
            request,
            "error.html",
            {
                "err": f"Extension {ext_id} not found",
                "message": "Please 'Refresh Preview' first.",
            },
            status_code=HTTPStatus.NOT_FOUND,
        )

    response = template_renderer().TemplateResponse(
        request,
        html_file_path.as_posix(),
        {
            "user": user.json(),
            "ajax": _is_ajax_request(request),
        },
    )

    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
    )
    return response


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


@generic_router.get("/manifest/{usr}.webmanifest")
async def manifest(request: Request, usr: str):
    host = urlparse(str(request.url)).netloc
    user = await get_user(usr)
    if not user:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    return {
        "short_name": settings.lnbits_site_title,
        "name": settings.lnbits_site_title + " Wallet",
        "icons": [
            {
                "src": (
                    settings.lnbits_custom_logo
                    if settings.lnbits_custom_logo
                    else "images/logos/lnbits.png"
                ),
                "sizes": "512x512",
                "type": "image/png",
            },
            {"src": "/static/favicon.ico", "sizes": "32x32", "type": "image/x-icon"},
            {
                "src": "/static/images/maskable_icon_x192.png",
                "type": "image/png",
                "sizes": "192x192",
                "purpose": "maskable",
            },
            {
                "src": "/static/images/maskable_icon_x512.png",
                "type": "image/png",
                "sizes": "512x512",
                "purpose": "maskable",
            },
            {
                "src": "/static/images/maskable_icon.png",
                "type": "image/png",
                "sizes": "1024x1024",
                "purpose": "maskable",
            },
        ],
        "screenshots": [
            {
                "src": "/static/images/screenshot_desktop.png",
                "sizes": "2394x1314",
                "type": "image/png",
                "form_factor": "wide",
                "label": "LNbits - Desktop screenshot",
            },
            {
                "src": "/static/images/screenshot_phone.png",
                "sizes": "1080x1739",
                "type": "image/png",
                "form_factor": "narrow",
                "label": "LNbits - Phone screenshot",
            },
        ],
        "start_url": f"/wallet?usr={usr}&wal={user.wallets[0].id}",
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
                "url": f"/wallet?usr={usr}&wal={wallet.id}",
                "icons": [
                    {
                        "src": "/static/images/maskable_icon_x96.png",
                        "sizes": "96x96",
                        "type": "image/png",
                    }
                ],
            }
            for wallet in user.wallets
        ],
        "url_handlers": [{"origin": f"https://{host}"}],
    }


admin_ui_checks = [Depends(check_admin), Depends(check_admin_ui)]


@generic_router.get("/payments")
@generic_router.get("/wallet")
@generic_router.get("/wallet/{wallet_id}")
@generic_router.get("/wallets")
@generic_router.get("/account")
@generic_router.get("/extensions")
@generic_router.get("/users", dependencies=admin_ui_checks)
@generic_router.get("/audit", dependencies=admin_ui_checks)
@generic_router.get("/node", dependencies=admin_ui_checks)
@generic_router.get("/admin", dependencies=admin_ui_checks)
@generic_router.get(
    "/extensions/builder", dependencies=[Depends(check_extension_builder)]
)
async def index(
    request: Request, user: User = Depends(check_user_exists)
) -> HTMLResponse:
    return template_renderer().TemplateResponse(
        request,
        "index.html",
        {
            "user": user.json(),
        },
    )


@generic_router.get("/")
@generic_router.get("/error")
@generic_router.get("/node/public")
@generic_router.get("/first_install", dependencies=[Depends(check_first_install)])
async def index_public(request: Request) -> HTMLResponse:
    return template_renderer().TemplateResponse(request, "index_public.html")


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

    lnurl = url_decode(lightning)

    async with httpx.AsyncClient() as client:
        check_callback_url(lnurl)
        res1 = await client.get(lnurl, timeout=2)
        res1.raise_for_status()
        data1 = res1.json()
        if data1.get("tag") != "withdrawRequest":
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Invalid lnurl. Expected tag=withdrawRequest",
            )
        if not data1.get("maxWithdrawable"):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Invalid lnurl. Expected maxWithdrawable",
            )
        account = await create_user_account()
        wallet = account.wallets[0]
        payment = await create_invoice(
            wallet_id=wallet.id,
            amount=data1.get("maxWithdrawable") / 1000,
            memo=data1.get("defaultDescription", "lnurl wallet withdraw"),
        )
        url = data1.get("callback")
        params = {"k1": data1.get("k1"), "pr": payment.bolt11}
        callback = url + ("&" if urlparse(url).query else "?") + urlencode(params)

        res2 = await client.get(callback, timeout=5)
        res2.raise_for_status()

    return RedirectResponse(
        f"/wallet?usr={account.id}&wal={wallet.id}",
    )


def _is_ajax_request(request: Request):
    return request.headers.get("X-Requested-With", None) == "XMLHttpRequest"
