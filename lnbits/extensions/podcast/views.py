from http import HTTPStatus

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import podcast_ext, podcast_renderer
from .crud import get_Podcast

templates = Jinja2Templates(directory="templates")


@podcast_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return podcast_renderer().TemplateResponse(
        "podcast/index.html", {"request": request, "user": user.dict()}
    )


@podcast_ext.get("/{pod_id}", response_class=HTMLResponse)
async def display(request: Request, pod_id):
    pod = await get_Podcast(pod_id)
    if not pod:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Podcast pod does not exist."
        )
    ctx = {"request": request, "lnurl": pod.lnurl(req=request)}
    return podcast_renderer().TemplateResponse("podcast/display.html", ctx)


@podcast_ext.get("/print/{pod_id}", response_class=HTMLResponse)
async def print_qr(request: Request, pod_id):
    pod = await get_Podcast(pod_id)
    if not pod:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Podcast pod does not exist."
        )
    ctx = {"request": request, "lnurl": pod.lnurl(req=request)}
    return podcast_renderer().TemplateResponse("podcast/feed.rss", ctx)
