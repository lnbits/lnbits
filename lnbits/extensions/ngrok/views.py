# type: ignore
from os import getenv

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from pyngrok import conf, ngrok

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import ngrok_ext, ngrok_renderer

templates = Jinja2Templates(directory="templates")


def log_event_callback(log):
    string = str(log)
    string2 = string[string.find('url="https') : string.find('url="https') + 80]
    if string2:
        string3 = string2
        string4 = string3[4:]
        global string5
        string5 = string4.replace('"', "")


conf.get_default().log_event_callback = log_event_callback

ngrok_authtoken = getenv("NGROK_AUTHTOKEN")
if ngrok_authtoken is not None:
    ngrok.set_auth_token(ngrok_authtoken)

port = getenv("PORT")
ngrok_tunnel = ngrok.connect(port)


@ngrok_ext.get("/")
async def index(request: Request, user: User = Depends(check_user_exists)):
    return ngrok_renderer().TemplateResponse(
        "ngrok/index.html", {"request": request, "ngrok": string5, "user": user.dict()}
    )
