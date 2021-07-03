from quart import g, render_template

from lnbits.decorators import check_user_exists, validate_uuids

from pyngrok import conf, ngrok

def log_event_callback(log):
    string = str(log)
    string2 = string[string.find('url="https'):string.find('url="https')+40]
    if string2:
        string3 = string2
        string4 = string3[4:]
        global string5
        string5 = string4.replace( '"', '' )

conf.get_default().log_event_callback = log_event_callback

ngrok_tunnel = ngrok.connect(5000)

from . import freetunnel_ext

@freetunnel_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()

async def index():
#    row = await db.fetchone("SELECT * FROM ngrok")

#    return row
#    return "Access and use your lnbits instance here: " + string5
#    return Ngrok.from_row(row) if row else None
    return await render_template("freetunnel/index.html", ngrok=string5)
