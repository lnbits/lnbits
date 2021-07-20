from quart import g, render_template

from lnbits.decorators import check_user_exists, validate_uuids

from pyngrok import conf, ngrok
from . import ngrok_ext
from os import getenv


def log_event_callback(log):
    string = str(log)
    string2 = string[string.find('url="https') : string.find('url="https') + 40]
    if string2:
        string3 = string2
        string4 = string3[4:]
        global string5
        string5 = string4.replace('"', "")


conf.get_default().log_event_callback = log_event_callback

port = getenv("PORT")
ngrok_tunnel = ngrok.connect(port)


@ngrok_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("ngrok/index.html", ngrok=string5, user=g.user)
