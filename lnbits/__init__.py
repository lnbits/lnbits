import importlib
import json
import requests
import uuid

from flask import g, Flask, jsonify, redirect, render_template, request, url_for
from flask_assets import Environment, Bundle
from flask_compress import Compress
from flask_talisman import Talisman
from lnurl import Lnurl, LnurlWithdrawResponse

from . import bolt11
from .core import core_app
from .decorators import api_validate_post_request
from .db import init_databases, open_db
from .helpers import ExtensionManager, megajson
from .settings import WALLET, DEFAULT_USER_WALLET_NAME, FEE_RESERVE


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


@app.route("/api/v1/channels/transactions", methods=["GET", "POST"])
@api_validate_post_request(required_params=["payment_request"])
def api_transactions():

    with open_db() as db:
        wallet = db.fetchone("SELECT id FROM wallets WHERE adminkey = ?", (request.headers["Grpc-Metadata-macaroon"],))

        if not wallet:
            return jsonify({"message": "BAD AUTH"}), 401

        # decode the invoice
        invoice = bolt11.decode(g.data["payment_request"])
        if invoice.amount_msat == 0:
            return jsonify({"message": "AMOUNTLESS INVOICES NOT SUPPORTED"}), 400

        # insert the payment
        db.execute(
            "INSERT OR IGNORE INTO apipayments (payhash, amount, fee, wallet, pending, memo) VALUES (?, ?, ?, ?, 1, ?)",
            (
                invoice.payment_hash,
                -int(invoice.amount_msat),
                -int(invoice.amount_msat) * FEE_RESERVE,
                wallet["id"],
                invoice.description,
            ),
        )

        # check balance
        balance = db.fetchone("SELECT balance/1000 FROM balances WHERE wallet = ?", (wallet["id"],))[0]
        if balance < 0:
            db.execute("DELETE FROM apipayments WHERE payhash = ? AND wallet = ?", (invoice.payment_hash, wallet["id"]))
            return jsonify({"message": "INSUFFICIENT BALANCE"}), 403

        # check if the invoice is an internal one
        if db.fetchone("SELECT count(*) FROM apipayments WHERE payhash = ?", (invoice.payment_hash,))[0] == 2:
            # internal. mark both sides as fulfilled.
            db.execute("UPDATE apipayments SET pending = 0, fee = 0 WHERE payhash = ?", (invoice.payment_hash,))
        else:
            # actually send the payment
            r = WALLET.pay_invoice(g.data["payment_request"])

            if not r.raw_response.ok or r.failed:
                return jsonify({"message": "UNEXPECTED PAYMENT ERROR"}), 500

            # payment went through, not pending anymore, save actual fees
            db.execute(
                "UPDATE apipayments SET pending = 0, fee = ? WHERE payhash = ? AND wallet = ?",
                (r.fee_msat, invoice.payment_hash, wallet["id"]),
            )

    return jsonify({"PAID": "TRUE", "payment_hash": invoice.payment_hash}), 200


@app.route("/api/v1/checkpending", methods=["POST"])
def api_checkpending():
    with open_db() as db:
        for pendingtx in db.fetchall(
            """
            SELECT
                payhash,
                CASE
                    WHEN amount < 0 THEN 'send'
                    ELSE 'recv'
                END AS kind
            FROM apipayments
            INNER JOIN wallets ON apipayments.wallet = wallets.id
            WHERE time > strftime('%s', 'now') - 86400
                AND pending = 1
                AND (adminkey = ? OR inkey = ?)
            """,
            (request.headers["Grpc-Metadata-macaroon"], request.headers["Grpc-Metadata-macaroon"]),
        ):
            payhash = pendingtx["payhash"]
            kind = pendingtx["kind"]

            if kind == "send":
                payment_complete = WALLET.get_payment_status(payhash).settled
                if payment_complete:
                    db.execute("UPDATE apipayments SET pending = 0 WHERE payhash = ?", (payhash,))
                elif payment_complete is False:
                    db.execute("DELETE FROM apipayments WHERE payhash = ?", (payhash,))

            elif kind == "recv" and WALLET.get_invoice_status(payhash).settled:
                db.execute("UPDATE apipayments SET pending = 0 WHERE payhash = ?", (payhash,))

    return ""


if __name__ == '__main__':
    app.run()
