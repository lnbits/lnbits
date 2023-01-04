from http import HTTPStatus

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
async def wallet(request: Request, mint_id: str):
    cashu = await get_cashu(mint_id)
    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )
    return cashu_renderer().TemplateResponse(
        "cashu/wallet.html",
        {
            "request": request,
            "web_manifest": f"/cashu/manifest/{mint_id}.webmanifest",
            "mint_name": cashu.name,
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
        {"request": request, "mint_name": cashu.name, "mint_id": mintID},
    )


@cashu_ext.get("/manifest/{cashu_id}.webmanifest")
async def manifest(cashu_id: str):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )

    return {
        "short_name": "Cashu",
        "name": "Cashu" + " - " + cashu.name,
        "icons": [
            {
                "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/android/android-launchericon-512-512.png",
                "type": "image/png",
                "sizes": "512x512",
            },
            {
                "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/android/android-launchericon-96-96.png",
                "type": "image/png",
                "sizes": "96x96",
            },
        ],
        "id": "/cashu/wallet?mint_id=" + cashu_id,
        "start_url": "/cashu/wallet?mint_id=" + cashu_id,
        "background_color": "#1F2234",
        "description": "Cashu ecash wallet",
        "display": "standalone",
        "scope": "/cashu/",
        "theme_color": "#1F2234",
        "protocol_handlers": [
            {"protocol": "cashu", "url": "&recv_token=%s"},
            {"protocol": "lightning", "url": "&lightning=%s"},
        ],
        "shortcuts": [
            {
                "name": "Cashu" + " - " + cashu.name,
                "short_name": "Cashu",
                "description": "Cashu" + " - " + cashu.name,
                "url": "/cashu/wallet?mint_id=" + cashu_id,
                "icons": [
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/android/android-launchericon-512-512.png",
                        "sizes": "512x512",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/android/android-launchericon-192-192.png",
                        "sizes": "192x192",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/android/android-launchericon-144-144.png",
                        "sizes": "144x144",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/android/android-launchericon-96-96.png",
                        "sizes": "96x96",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/android/android-launchericon-72-72.png",
                        "sizes": "72x72",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/android/android-launchericon-48-48.png",
                        "sizes": "48x48",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/16.png",
                        "sizes": "16x16",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/20.png",
                        "sizes": "20x20",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/29.png",
                        "sizes": "29x29",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/32.png",
                        "sizes": "32x32",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/40.png",
                        "sizes": "40x40",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/50.png",
                        "sizes": "50x50",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/57.png",
                        "sizes": "57x57",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/58.png",
                        "sizes": "58x58",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/60.png",
                        "sizes": "60x60",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/64.png",
                        "sizes": "64x64",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/72.png",
                        "sizes": "72x72",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/76.png",
                        "sizes": "76x76",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/80.png",
                        "sizes": "80x80",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/87.png",
                        "sizes": "87x87",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/100.png",
                        "sizes": "100x100",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/114.png",
                        "sizes": "114x114",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/120.png",
                        "sizes": "120x120",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/128.png",
                        "sizes": "128x128",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/144.png",
                        "sizes": "144x144",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/152.png",
                        "sizes": "152x152",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/167.png",
                        "sizes": "167x167",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/180.png",
                        "sizes": "180x180",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/192.png",
                        "sizes": "192x192",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/256.png",
                        "sizes": "256x256",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/512.png",
                        "sizes": "512x512",
                    },
                    {
                        "src": "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/circle/ios/1024.png",
                        "sizes": "1024x1024",
                    },
                ],
            }
        ],
    }
