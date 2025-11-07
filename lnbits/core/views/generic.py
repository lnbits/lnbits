from hashlib import sha256
from http import HTTPStatus
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import Cookie, Depends, Query, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.routing import APIRouter
from lnurl import url_decode
from pydantic.types import UUID4

from lnbits.core.helpers import to_valid_user_id
from lnbits.core.models import User
from lnbits.core.models.extensions import ExtensionMeta, InstallableExtension
from lnbits.core.services import create_invoice, create_user_account
from lnbits.core.services.extensions import get_valid_extensions
from lnbits.decorators import (
    check_admin,
    check_admin_ui,
    check_extension_builder,
    check_user_exists,
)
from lnbits.helpers import check_callback_url, template_renderer
from lnbits.settings import settings

from ...utils.exchange_rates import allowed_currencies
from ..crud import (
    create_wallet,
    get_db_versions,
    get_installed_extensions,
    get_user,
    get_wallet,
)

generic_router = APIRouter(
    tags=["Core NON-API Website Routes"], include_in_schema=False
)


@generic_router.get("/favicon.ico", response_class=FileResponse)
async def favicon():
    return RedirectResponse(settings.lnbits_qr_logo)


@generic_router.get("/", response_class=HTMLResponse)
async def home(request: Request, lightning: str = ""):
    return template_renderer().TemplateResponse(
        request, "core/index.html", {"lnurl": lightning}
    )


@generic_router.get(
    "/wallet",
    response_class=HTMLResponse,
    description="show wallet page",
)
async def get_user_wallet(
    request: Request,
    lnbits_last_active_wallet: Annotated[str | None, Cookie()] = None,
    user: User = Depends(check_user_exists),
    wal: UUID4 | None = Query(None),
):
    if wal:
        wallet = await get_wallet(wal.hex)
    elif len(user.wallets) == 0:
        wallet = await create_wallet(user_id=user.id)
        user.wallets.append(wallet)
    elif lnbits_last_active_wallet and user.get_wallet(lnbits_last_active_wallet):
        wallet = await get_wallet(lnbits_last_active_wallet)
    else:
        wallet = user.wallets[0]

    if not wallet or wallet.deleted:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Wallet not found",
        )
    if wallet.user != user.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not your wallet.",
        )
    context = {
        "user": user.json(),
        "wallet": wallet.json(),
        "wallet_name": wallet.name,
        "currencies": allowed_currencies(),
        "service_fee": settings.lnbits_service_fee,
        "service_fee_max": settings.lnbits_service_fee_max,
        "web_manifest": f"/manifest/{user.id}.webmanifest",
    }

    return template_renderer().TemplateResponse(
        request,
        "core/wallet.html",
        {**context, "ajax": _is_ajax_request(request)},
    )


@generic_router.get("/first_install", response_class=HTMLResponse)
async def first_install(request: Request):
    if not settings.first_install:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Super user account has already been configured.",
        )
    return template_renderer().TemplateResponse(
        request,
        "core/first_install.html",
    )


@generic_router.get("/robots.txt", response_class=HTMLResponse)
async def robots():
    data = """
    User-agent: *
    Disallow: /
    """
    return HTMLResponse(content=data, media_type="text/plain")


@generic_router.get("/extensions", name="extensions", response_class=HTMLResponse)
async def extensions(request: Request, user: User = Depends(check_user_exists)):
    installed_exts: list[InstallableExtension] = await get_installed_extensions()
    installed_exts_ids = [e.id for e in installed_exts]

    installable_exts = await InstallableExtension.get_installable_extensions()
    installable_exts_ids = [e.id for e in installable_exts]
    installable_exts += [e for e in installed_exts if e.id not in installable_exts_ids]

    for e in installable_exts:
        installed_ext = next((ie for ie in installed_exts if e.id == ie.id), None)
        if installed_ext and installed_ext.meta:
            installed_release = installed_ext.meta.installed_release
            if installed_ext.meta.pay_to_enable and not user.admin:
                # not a security leak, but better not to share the wallet id
                installed_ext.meta.pay_to_enable.wallet = None
            pay_to_enable = installed_ext.meta.pay_to_enable

            if e.meta:
                e.meta.installed_release = installed_release
                e.meta.pay_to_enable = pay_to_enable
            else:
                e.meta = ExtensionMeta(
                    installed_release=installed_release,
                    pay_to_enable=pay_to_enable,
                )
            # use the installed extension values
            e.name = installed_ext.name
            e.short_description = installed_ext.short_description
            e.icon = installed_ext.icon

    all_ext_ids = [ext.code for ext in await get_valid_extensions()]
    inactive_extensions = [e.id for e in await get_installed_extensions(active=False)]
    db_versions = await get_db_versions()

    extension_data = [
        {
            "id": ext.id,
            "name": ext.name,
            "icon": ext.icon,
            "shortDescription": ext.short_description,
            "stars": ext.stars,
            "isFeatured": ext.meta.featured if ext.meta else False,
            "dependencies": ext.meta.dependencies if ext.meta else "",
            "isInstalled": ext.id in installed_exts_ids,
            "hasDatabaseTables": next(
                (True for version in db_versions if version.db == ext.id), False
            ),
            "isAvailable": ext.id in all_ext_ids,
            "isAdminOnly": ext.id in settings.lnbits_admin_extensions,
            "isActive": ext.id not in inactive_extensions,
            "latestRelease": (
                dict(ext.meta.latest_release)
                if ext.meta and ext.meta.latest_release
                else None
            ),
            "hasPaidRelease": ext.meta.has_paid_release if ext.meta else False,
            "hasFreeRelease": ext.meta.has_free_release if ext.meta else False,
            "paidFeatures": ext.meta.paid_features if ext.meta else False,
            "installedRelease": (
                dict(ext.meta.installed_release)
                if ext.meta and ext.meta.installed_release
                else None
            ),
            "payToEnable": (
                dict(ext.meta.pay_to_enable)
                if ext.meta and ext.meta.pay_to_enable
                else {}
            ),
            "isPaymentRequired": ext.requires_payment,
        }
        for ext in installable_exts
    ]

    # refresh user state. Eg: enabled extensions.
    # TODO: refactor
    # user = await get_user(user.id) or user

    return template_renderer().TemplateResponse(
        request,
        "core/extensions.html",
        {
            "user": user.json(),
            "extension_data": extension_data,
            "extension_builder_enabled": user.admin
            or settings.lnbits_extensions_builder_activate_non_admins,
            "ajax": _is_ajax_request(request),
        },
    )


@generic_router.get(
    "/extensions/builder",
    name="extensions builder",
    dependencies=[Depends(check_extension_builder)],
)
async def extensions_builder(
    request: Request, user: User = Depends(check_user_exists)
) -> HTMLResponse:
    return template_renderer().TemplateResponse(
        request,
        "core/extensions_builder.html",
        {
            "user": user.json(),
            "ajax": _is_ajax_request(request),
        },
    )


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
                    else "https://cdn.jsdelivr.net/gh/lnbits/lnbits@main/docs/logos/lnbits.png"
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
@generic_router.get("/wallets")
@generic_router.get("/account")
@generic_router.get("/users", dependencies=admin_ui_checks)
@generic_router.get("/audit", dependencies=admin_ui_checks)
@generic_router.get("/node", dependencies=admin_ui_checks)
@generic_router.get("/admin", dependencies=admin_ui_checks)
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


@generic_router.get("/node/public")
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
