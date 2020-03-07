import importlib
import json
import requests
import uuid

from flask import Flask, redirect, render_template, request, url_for
from flask_assets import Environment, Bundle
from flask_compress import Compress
from flask_talisman import Talisman
from lnurl import Lnurl, LnurlWithdrawResponse

from .core import core_app
from .db import init_databases, open_db
from .helpers import ExtensionManager, megajson
from .settings import WALLET, DEFAULT_USER_WALLET_NAME


app = Flask(__name__)
valid_extensions = [ext for ext in ExtensionManager().extensions if ext.is_valid]


# optimization & security
# -----------------------

Compress(app)
Talisman(
    app,
    content_security_policy={
        "default-src": [
            "'self'",
            "'unsafe-eval'",
            "'unsafe-inline'",
            "cdnjs.cloudflare.com",
            "code.ionicframework.com",
            "code.jquery.com",
            "fonts.googleapis.com",
            "fonts.gstatic.com",
            "maxcdn.bootstrapcdn.com",
            "github.com",
            "avatars2.githubusercontent.com",
        ]
    },
)


# blueprints / extensions
# -----------------------

app.register_blueprint(core_app)

for ext in valid_extensions:
    try:
        ext_module = importlib.import_module(f"lnbits.extensions.{ext.code}")
        app.register_blueprint(getattr(ext_module, f"{ext.code}_ext"), url_prefix=f"/{ext.code}")
    except Exception:
        raise ImportError(f"Please make sure that the extension `{ext.code}` follows conventions.")


# filters
# -------

app.jinja_env.globals["DEBUG"] = app.config["DEBUG"]
app.jinja_env.globals["EXTENSIONS"] = valid_extensions
app.jinja_env.filters["megajson"] = megajson


# assets
# ------

assets = Environment(app)
assets.url = app.static_url_path
assets.register("base_css", Bundle("scss/base.scss", filters="pyscss", output="css/base.css"))


# init
# ----


@app.before_first_request
def init():
    init_databases()


# vvvvvvvvvvvvvvvvvvvvvvvvvvv
# move the rest to `core_app`
# vvvvvvvvvvvvvvvvvvvvvvvvvvv
# vvvvvvvvvvvvvvvvvvvvvvvvvvv


@app.route("/lnurl")
def lnurl():
    lnurl = request.args.get("lightning")
    return render_template("lnurl.html", lnurl=lnurl)


@app.route("/lnurlwallet")
def lnurlwallet():
    lnurl = Lnurl(request.args.get("lightning"))
    r = requests.get(lnurl.url)
    if not r.ok:
        return redirect(url_for("home"))

    data = json.loads(r.text)
    if data.get("status") == "ERROR":
        return redirect(url_for("home"))

    withdraw_res = LnurlWithdrawResponse(**data)

    _, pay_hash, pay_req = WALLET.create_invoice(withdraw_res.max_sats, "LNbits lnurl funding")

    r = requests.get(
        withdraw_res.callback.base,
        params={**withdraw_res.callback.query_params, **{"k1": withdraw_res.k1, "pr": pay_req}},
    )

    if not r.ok:
        return redirect(url_for("home"))
    data = json.loads(r.text)

    for i in range(10):
        r = WALLET.get_invoice_status(pay_hash).raw_response
        if not r.ok:
            continue

        data = r.json()
        break

    with open_db() as db:
        wallet_id = uuid.uuid4().hex
        user_id = uuid.uuid4().hex
        wallet_name = DEFAULT_USER_WALLET_NAME
        adminkey = uuid.uuid4().hex
        inkey = uuid.uuid4().hex

        db.execute("INSERT INTO accounts (id) VALUES (?)", (user_id,))
        db.execute(
            "INSERT INTO wallets (id, name, user, adminkey, inkey) VALUES (?, ?, ?, ?, ?)",
            (wallet_id, wallet_name, user_id, adminkey, inkey),
        )
        db.execute(
            "INSERT INTO apipayments (payhash, amount, wallet, pending, memo) VALUES (?, ?, ?, 0, ?)",
            (pay_hash, withdraw_res.max_sats * 1000, wallet_id, "LNbits lnurl funding",),
        )

    return redirect(url_for("wallet", usr=user_id, wal=wallet_id))


if __name__ == '__main__':
    app.run()
