import sys
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, List, Optional, Union
from urllib.parse import urlparse

from fastapi import Cookie, Depends, Query, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.routing import APIRouter
from loguru import logger
from pydantic.types import UUID4

from lnbits.core.db import core_app_extra
from lnbits.core.helpers import to_valid_user_id
from lnbits.core.models import User
from lnbits.decorators import check_admin, check_user_exists
from lnbits.helpers import template_renderer
from lnbits.settings import settings
from lnbits.wallets import get_funding_source

from ...extension_manager import InstallableExtension, get_valid_extensions
from ...utils.exchange_rates import allowed_currencies, currencies
from ..crud import (
    create_wallet,
    get_dbversions,
    get_inactive_extensions,
    get_installed_extensions,
    get_user,
    update_installed_extension_state,
    update_user_extension,
)

generic_router = APIRouter(
    tags=["Core NON-API Website Routes"], include_in_schema=False
)


@generic_router.get("/favicon.ico", response_class=FileResponse)
async def favicon():
    return FileResponse(Path("lnbits", "static", "favicon.ico"))


@generic_router.get("/", response_class=HTMLResponse)
async def home(request: Request, lightning: str = ""):
    return template_renderer().TemplateResponse(
        request, "core/index.html", {"lnurl": lightning}
    )


@generic_router.get("/first_install", response_class=HTMLResponse)
async def first_install(request: Request):
    if not settings.first_install:
        return template_renderer().TemplateResponse(
            request,
            "error.html",
            {
                "err": "Super user account has already been configured.",
            },
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


@generic_router.get(
    "/extensions", name="install.extensions", response_class=HTMLResponse
)
async def extensions_install(
    request: Request,
    user: User = Depends(check_user_exists),
    activate: str = Query(None),
    deactivate: str = Query(None),
    enable: str = Query(None),
    disable: str = Query(None),
):
    await toggle_extension(enable, disable, user.id)

    try:
        installed_exts: List["InstallableExtension"] = await get_installed_extensions()
        installed_exts_ids = [e.id for e in installed_exts]

        installable_exts = await InstallableExtension.get_installable_extensions()
        installable_exts_ids = [e.id for e in installable_exts]
        installable_exts += [
            e for e in installed_exts if e.id not in installable_exts_ids
        ]

        for e in installable_exts:
            installed_ext = next((ie for ie in installed_exts if e.id == ie.id), None)
            if installed_ext:
                e.installed_release = installed_ext.installed_release
                # use the installed extension values
                e.name = installed_ext.name
                e.short_description = installed_ext.short_description
                e.icon = installed_ext.icon

    except Exception as ex:
        logger.warning(ex)
        installable_exts = []
        installed_exts_ids = []

    try:
        ext_id = activate or deactivate
        all_extensions = get_valid_extensions()
        ext = next((e for e in all_extensions if e.code == ext_id), None)
        if ext_id and user.admin:
            if deactivate and deactivate not in settings.lnbits_deactivated_extensions:
                settings.lnbits_deactivated_extensions += [deactivate]
            elif activate:
                # if extension never loaded (was deactivated on server startup)
                if ext_id not in sys.modules.keys():
                    # run extension start-up routine
                    core_app_extra.register_new_ext_routes(ext)

                settings.lnbits_deactivated_extensions = list(
                    filter(
                        lambda e: e != activate, settings.lnbits_deactivated_extensions
                    )
                )

            await update_installed_extension_state(
                ext_id=ext_id, active=activate is not None
            )

        all_ext_ids = [ext.code for ext in all_extensions]
        inactive_extensions = await get_inactive_extensions()
        db_version = await get_dbversions()
        extensions = [
            {
                "id": ext.id,
                "name": ext.name,
                "icon": ext.icon,
                "shortDescription": ext.short_description,
                "stars": ext.stars,
                "isFeatured": ext.featured,
                "dependencies": ext.dependencies,
                "isInstalled": ext.id in installed_exts_ids,
                "hasDatabaseTables": ext.id in db_version,
                "isAvailable": ext.id in all_ext_ids,
                "isAdminOnly": ext.id in settings.lnbits_admin_extensions,
                "isActive": ext.id not in inactive_extensions,
                "latestRelease": (
                    dict(ext.latest_release) if ext.latest_release else None
                ),
                "installedRelease": (
                    dict(ext.installed_release) if ext.installed_release else None
                ),
            }
            for ext in installable_exts
        ]

        # refresh user state. Eg: enabled extensions.
        user = await get_user(user.id) or user

        return template_renderer().TemplateResponse(
            request,
            "core/extensions.html",
            {
                "user": user.dict(),
                "extensions": extensions,
            },
        )
    except Exception as exc:
        logger.warning(exc)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@generic_router.get(
    "/wallet",
    response_class=HTMLResponse,
    description="show wallet page",
)
async def wallet(
    request: Request,
    lnbits_last_active_wallet: Annotated[Union[str, None], Cookie()] = None,
    user: User = Depends(check_user_exists),
    wal: Optional[UUID4] = Query(None),
):
    if wal:
        wallet_id = wal.hex
    elif len(user.wallets) == 0:
        wallet = await create_wallet(user_id=user.id)
        user = await get_user(user_id=user.id) or user
        wallet_id = wallet.id
    elif lnbits_last_active_wallet and user.get_wallet(lnbits_last_active_wallet):
        wallet_id = lnbits_last_active_wallet
    else:
        wallet_id = user.wallets[0].id

    user_wallet = user.get_wallet(wallet_id)
    if not user_wallet or user_wallet.deleted:
        return template_renderer().TemplateResponse(
            request, "error.html", {"err": "Wallet not found"}
        )

    resp = template_renderer().TemplateResponse(
        request,
        "core/wallet.html",
        {
            "user": user.dict(),
            "wallet": user_wallet.dict(),
            "currencies": allowed_currencies(),
            "service_fee": settings.lnbits_service_fee,
            "service_fee_max": settings.lnbits_service_fee_max,
            "web_manifest": f"/manifest/{user.id}.webmanifest",
        },
    )
    resp.set_cookie("lnbits_last_active_wallet", wallet_id)
    return resp


@generic_router.get(
    "/account",
    response_class=HTMLResponse,
    description="show account page",
)
async def account(
    request: Request,
    user: User = Depends(check_user_exists),
):
    return template_renderer().TemplateResponse(
        request,
        "core/account.html",
        {
            "user": user.dict(),
        },
    )


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


@generic_router.get("/node", response_class=HTMLResponse)
async def node(request: Request, user: User = Depends(check_admin)):
    if not settings.lnbits_node_ui:
        raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE)

    funding_source = get_funding_source()
    _, balance = await funding_source.status()

    return template_renderer().TemplateResponse(
        request,
        "node/index.html",
        {
            "user": user.dict(),
            "settings": settings.dict(),
            "balance": balance,
            "wallets": user.wallets[0].dict(),
        },
    )


@generic_router.get("/node/public", response_class=HTMLResponse)
async def node_public(request: Request):
    if not settings.lnbits_public_node_ui:
        raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE)

    funding_source = get_funding_source()
    _, balance = await funding_source.status()

    return template_renderer().TemplateResponse(
        request,
        "node/public.html",
        {
            "settings": settings.dict(),
            "balance": balance,
        },
    )


@generic_router.get("/admin", response_class=HTMLResponse)
async def admin_index(request: Request, user: User = Depends(check_admin)):
    if not settings.lnbits_admin_ui:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    funding_source = get_funding_source()
    _, balance = await funding_source.status()

    return template_renderer().TemplateResponse(
        request,
        "admin/index.html",
        {
            "user": user.dict(),
            "settings": settings.dict(),
            "balance": balance,
            "currencies": list(currencies.keys()),
        },
    )


@generic_router.get("/users", response_class=HTMLResponse)
async def users_index(request: Request, user: User = Depends(check_admin)):
    if not settings.lnbits_admin_ui:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    return template_renderer().TemplateResponse(
        "users/index.html",
        {
            "request": request,
            "user": user.dict(),
            "settings": settings.dict(),
            "currencies": list(currencies.keys()),
        },
    )


@generic_router.get("/uuidv4/{hex_value}")
async def hex_to_uuid4(hex_value: str):
    try:
        user_id = to_valid_user_id(hex_value).hex
        return RedirectResponse(url=f"/wallet?usr={user_id}")
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


async def toggle_extension(extension_to_enable, extension_to_disable, user_id):
    if extension_to_enable and extension_to_disable:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "You can either `enable` or `disable` an extension."
        )

    # check if extension exists
    if extension_to_enable or extension_to_disable:
        ext = extension_to_enable or extension_to_disable
        if ext not in [e.code for e in get_valid_extensions()]:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST, f"Extension '{ext}' doesn't exist."
            )

    if extension_to_enable:
        logger.info(f"Enabling extension: {extension_to_enable} for user {user_id}")
        await update_user_extension(
            user_id=user_id, extension=extension_to_enable, active=True
        )
    elif extension_to_disable:
        logger.info(f"Disabling extension: {extension_to_disable} for user {user_id}")
        await update_user_extension(
            user_id=user_id, extension=extension_to_disable, active=False
        )
