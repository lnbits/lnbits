from http import HTTPStatus

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.settings import LNBITS_CUSTOM_LOGO, LNBITS_SITE_TITLE

from . import cashu_ext, cashu_renderer
from .crud import get_cashu

templates = Jinja2Templates(directory="templates")


@cashu_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return cashu_renderer().TemplateResponse(
        "cashu/index.html", {"request": request, "user": user.dict()}
    )


# @cashu_ext.get("/wallet")
# async def wallet(request: Request):
#     return cashu_renderer().TemplateResponse("cashu/wallet.html", {"request": request})


@cashu_ext.get("/wallet")
async def wallet(request: Request, mint_id: str):
    return cashu_renderer().TemplateResponse(
        "cashu/wallet.html",
        {
            "request": request,
            "web_manifest": f"/cashu/manifest/{mint_id}.webmanifest",
        },
    )


@cashu_ext.get("/mint/{mintID}")
async def cashu(request: Request, mintID):
    cashu = await get_cashu(mintID)
    return cashu_renderer().TemplateResponse(
        "cashu/mint.html", {"request": request, "mint_name": cashu.name}
    )


@cashu_ext.get("/manifest/{cashu_id}.webmanifest")
async def manifest(cashu_id: str):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )

    return {
        "short_name": "Cashu",
        "name": cashu.name + " - " + "Cashu",
        "icons": [
            {
                "src": LNBITS_CUSTOM_LOGO
                if LNBITS_CUSTOM_LOGO
                else "https://github.com/cashubtc/cashu-ui/raw/main/ui/icons/96x96.png",
                "type": "image/png",
                "sizes": "96x96",
            }
        ],
        "start_url": "/cashu/wallet?mint_id=" + cashu_id,
        "background_color": "#1F2234",
        "description": "Cashu ecash wallet",
        "display": "standalone",
        "scope": "/cashu/",
        "theme_color": "#1F2234",
        "shortcuts": [
            {
                "name": cashu.name + " - " + "Cashu wallet",
                "short_name": cashu.name,
                "description": cashu.name + " - " + "Cashu wallet",
                "url": "/cashu/wallet?mint_id=" + cashu_id,
            }
        ],
    }
