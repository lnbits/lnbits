from http import HTTPStatus
from typing import Optional

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import cashu_ext, cashu_renderer
from .crud import get_cashu

templates = Jinja2Templates(directory="templates")


@cashu_ext.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    user: User = Depends(check_user_exists),
):
    return cashu_renderer().TemplateResponse(
        "cashu/index.html", {"request": request, "user": user.dict()}
    )


@cashu_ext.get("/wallet")
async def wallet(request: Request, mint_id: Optional[str] = None):
    if mint_id is not None:
        cashu = await get_cashu(mint_id)
        if not cashu:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
            )
        manifest_url = f"/cashu/manifest/{mint_id}.webmanifest"
        mint_name = cashu.name
    else:
        manifest_url = "/cashu/cashu.webmanifest"
        mint_name = "Cashu mint"

    return cashu_renderer().TemplateResponse(
        "cashu/wallet.html",
        {
            "request": request,
            "web_manifest": manifest_url,
            "mint_name": mint_name,
        },
    )


@cashu_ext.get("/mint/{mintID}")
async def cashu(request: Request, mintID):
    cashu = await get_cashu(mintID)
    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )
    return cashu_renderer().TemplateResponse(
        "cashu/mint.html",
        {"request": request, "mint_id": mintID},
    )


@cashu_ext.get("/manifest/{cashu_id}.webmanifest")
async def manifest_lnbits(cashu_id: str):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )

    return get_manifest(cashu_id, cashu.name)


@cashu_ext.get("/cashu.webmanifest")
async def manifest():
    return get_manifest()


def get_manifest(mint_id: Optional[str] = None, mint_name: Optional[str] = None):
    manifest_name = "Cashu"
    if mint_name:
        manifest_name += " - " + mint_name
    manifest_url = "/cashu/wallet"
    if mint_id:
        manifest_url += "?mint_id=" + mint_id

    return {
        "short_name": "Cashu",
        "name": manifest_name,
        "icons": [
            {
                "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/512x512.png",
                "type": "image/png",
                "sizes": "512x512",
            },
            {
                "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/96x96.png",
                "type": "image/png",
                "sizes": "96x96",
            },
        ],
        "id": manifest_url,
        "start_url": manifest_url,
        "background_color": "#1F2234",
        "description": "Cashu ecash wallet",
        "display": "standalone",
        "scope": "/cashu/",
        "theme_color": "#1F2234",
        "protocol_handlers": [
            {"protocol": "web+cashu", "url": "&recv_token=%s"},
            {"protocol": "web+lightning", "url": "&lightning=%s"},
        ],
        "shortcuts": [
            {
                "name": manifest_name,
                "short_name": "Cashu",
                "description": manifest_name,
                "url": manifest_url,
                "icons": [
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/512x512.png",
                        "sizes": "512x512",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/192x192.png",
                        "sizes": "192x192",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/144x144.png",
                        "sizes": "144x144",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/96x96.png",
                        "sizes": "96x96",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/72x72.png",
                        "sizes": "72x72",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/48x48.png",
                        "sizes": "48x48",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/16x16.png",
                        "sizes": "16x16",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/20x20.png",
                        "sizes": "20x20",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/29x29.png",
                        "sizes": "29x29",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/32x32.png",
                        "sizes": "32x32",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/40x40.png",
                        "sizes": "40x40",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/50x50.png",
                        "sizes": "50x50",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/57x57.png",
                        "sizes": "57x57",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/58x58.png",
                        "sizes": "58x58",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/60x60.png",
                        "sizes": "60x60",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/64x64.png",
                        "sizes": "64x64",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/72x72.png",
                        "sizes": "72x72",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/76x76.png",
                        "sizes": "76x76",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/80x80.png",
                        "sizes": "80x80",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/87x87.png",
                        "sizes": "87x87",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/100x100.png",
                        "sizes": "100x100",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/114x114.png",
                        "sizes": "114x114",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/120x120.png",
                        "sizes": "120x120",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/128x128.png",
                        "sizes": "128x128",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/144x144.png",
                        "sizes": "144x144",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/152x152.png",
                        "sizes": "152x152",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/167x167.png",
                        "sizes": "167x167",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/180x180.png",
                        "sizes": "180x180",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/192x192.png",
                        "sizes": "192x192",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/256x256.png",
                        "sizes": "256x256",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/512x512.png",
                        "sizes": "512x512",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/1024x1024.png",
                        "sizes": "1024x1024",
                    },
                ],
            }
        ],
    }
