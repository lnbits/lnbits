import json
import os
import requests
import uuid

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_talisman import Talisman
from lnurl import Lnurl, LnurlWithdrawResponse

from . import bolt11
from .core import core_app
from .db import open_db, open_ext_db
from .extensions.withdraw import withdraw_ext
from .helpers import megajson
from .settings import LNBITS_PATH, WALLET, DEFAULT_USER_WALLET_NAME, FEE_RESERVE


app = Flask(__name__)


# filters
app.jinja_env.filters["megajson"] = megajson

# blueprints
app.register_blueprint(core_app)
app.register_blueprint(withdraw_ext, url_prefix="/withdraw")


@app.before_first_request
def init():
    with open_db() as db:
        with open(os.path.join(LNBITS_PATH, "data", "schema.sql")) as schemafile:
            for stmt in schemafile.read().split(";\n\n"):
                db.execute(stmt, [])


@app.route("/deletewallet")
def deletewallet():
    user_id = request.args.get("usr")
    wallet_id = request.args.get("wal")

    with open_db() as db:
        db.execute(
            """
            UPDATE wallets AS w
            SET
                user = 'del:' || w.user,
                adminkey = 'del:' || w.adminkey,
                inkey = 'del:' || w.inkey
            WHERE id = ? AND user = ?
            """,
            (wallet_id, user_id),
        )

        next_wallet = db.fetchone("SELECT id FROM wallets WHERE user = ?", (user_id,))

        if next_wallet:
            return redirect(url_for("wallet", usr=user_id, wal=next_wallet[0]))

    return redirect(url_for("home"))


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


@app.route("/wallet")
def wallet():
    usr = request.args.get("usr")
    wallet_id = request.args.get("wal")
    wallet_name = request.args.get("nme")

    if usr:
        if not len(usr) > 20:
            return redirect(url_for("home"))
    if wallet_id:
        if not len(wallet_id) > 20:
            return redirect(url_for("home"))

    # just usr: return a the first user wallet or create one if none found
    # usr and wallet_id: return that wallet or create it if it doesn't exist
    # usr, wallet_id and wallet_name: same as above, but use the specified name
    # usr and wallet_name: generate a wallet_id and create
    # wallet_id and wallet_name: create a user, then move an existing wallet or create
    # just wallet_name: create a user, then generate a wallet_id and create
    # nothing: create everything

    with open_db() as db:
        # ensure this user exists
        # -------------------------------

        if not usr:
            usr = uuid.uuid4().hex
            return redirect(url_for("wallet", usr=usr, wal=wallet_id, nme=wallet_name))

        db.execute(
            """
            INSERT OR IGNORE INTO accounts (id) VALUES (?)
            """,
            (usr,),
        )

        user_wallets = db.fetchall("SELECT * FROM wallets WHERE user = ?", (usr,))

        if not wallet_id:
            if user_wallets and not wallet_name:
                # fetch the first wallet from this user
                # -------------------------------------
                wallet_id = user_wallets[0]["id"]
            else:
                # create for this user
                # --------------------
                wallet_name = wallet_name or DEFAULT_USER_WALLET_NAME
                wallet_id = uuid.uuid4().hex
                db.execute(
                    """
                    INSERT INTO wallets (id, name, user, adminkey, inkey)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (wallet_id, wallet_name, usr, uuid.uuid4().hex, uuid.uuid4().hex),
                )

            return redirect(url_for("wallet", usr=usr, wal=wallet_id, nme=wallet_name))

        # if wallet_id is given, try to move it to this user or create
        # ------------------------------------------------------------
        db.execute(
            """
            INSERT OR REPLACE INTO wallets (id, user, name, adminkey, inkey)
            VALUES (?, ?,
                coalesce((SELECT name FROM wallets WHERE id = ?), ?),
                coalesce((SELECT adminkey FROM wallets WHERE id = ?), ?),
                coalesce((SELECT inkey FROM wallets WHERE id = ?), ?)
            )
            """,
            (
                wallet_id,
                usr,
                wallet_id,
                wallet_name or DEFAULT_USER_WALLET_NAME,
                wallet_id,
                uuid.uuid4().hex,
                wallet_id,
                uuid.uuid4().hex,
            ),
        )

        # finally, get the wallet with balance and transactions
        # -----------------------------------------------------

        wallet = db.fetchone(
            """
            SELECT
                coalesce((SELECT balance/1000 FROM balances WHERE wallet = wallets.id), 0) * ? AS balance,
                *
            FROM wallets
            WHERE user = ? AND id = ?
            """,
            (1 - FEE_RESERVE, usr, wallet_id),
        )

        transactions = db.fetchall(
            """
            SELECT *
            FROM apipayments
            WHERE wallet = ? AND pending = 0
            ORDER BY time
            """,
            (wallet_id,),
        )

    return render_template(
        "wallet.html", user_wallets=user_wallets, wallet=wallet, user=usr, transactions=transactions,
    )


@app.route("/api/v1/invoices", methods=["GET", "POST"])
def api_invoices():
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 400

    postedjson = request.json

    # Form validation
    if int(postedjson["value"]) < 0 or not postedjson["memo"].replace(" ", "").isalnum():
        return jsonify({"ERROR": "FORM ERROR"}), 401

    if "value" not in postedjson:
        return jsonify({"ERROR": "NO VALUE"}), 400

    if not postedjson["value"].isdigit():
        return jsonify({"ERROR": "VALUE MUST BE A NUMBER"}), 400

    if int(postedjson["value"]) < 0:
        return jsonify({"ERROR": "AMOUNTLESS INVOICES NOT SUPPORTED"}), 400

    if "memo" not in postedjson:
        return jsonify({"ERROR": "NO MEMO"}), 400

    with open_db() as db:
        wallet = db.fetchone(
            "SELECT id FROM wallets WHERE inkey = ? OR adminkey = ?",
            (request.headers["Grpc-Metadata-macaroon"], request.headers["Grpc-Metadata-macaroon"],),
        )

        if not wallet:
            return jsonify({"ERROR": "NO KEY"}), 200

        r, pay_hash, pay_req = WALLET.create_invoice(postedjson["value"], postedjson["memo"])

        if not r.ok or "error" in r.json():
            return jsonify({"ERROR": "UNEXPECTED BACKEND ERROR"}), 500

        amount_msat = int(postedjson["value"]) * 1000

        db.execute(
            "INSERT INTO apipayments (payhash, amount, wallet, pending, memo) VALUES (?, ?, ?, 1, ?)",
            (pay_hash, amount_msat, wallet["id"], postedjson["memo"],),
        )

    return jsonify({"pay_req": pay_req, "payment_hash": pay_hash}), 200


@app.route("/api/v1/channels/transactions", methods=["GET", "POST"])
def api_transactions():

    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 400

    data = request.json

    print(data)
    if "payment_request" not in data:
        return jsonify({"ERROR": "NO PAY REQ"}), 400

    with open_db() as db:
        wallet = db.fetchone("SELECT id FROM wallets WHERE adminkey = ?", (request.headers["Grpc-Metadata-macaroon"],))

        if not wallet:
            return jsonify({"ERROR": "BAD AUTH"}), 401

        # decode the invoice
        invoice = bolt11.decode(data["payment_request"])
        if invoice.amount_msat == 0:
            return jsonify({"ERROR": "AMOUNTLESS INVOICES NOT SUPPORTED"}), 400

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
            return jsonify({"ERROR": "INSUFFICIENT BALANCE"}), 403

        # check if the invoice is an internal one
        if db.fetchone("SELECT count(*) FROM apipayments WHERE payhash = ?", (invoice.payment_hash,))[0] == 2:
            # internal. mark both sides as fulfilled.
            db.execute("UPDATE apipayments SET pending = 0, fee = 0 WHERE payhash = ?", (invoice.payment_hash,))
        else:
            # actually send the payment
            r = WALLET.pay_invoice(data["payment_request"])

            if not r.raw_response.ok or r.failed:
                return jsonify({"ERROR": "UNEXPECTED PAYMENT ERROR"}), 500

            # payment went through, not pending anymore, save actual fees
            db.execute(
                "UPDATE apipayments SET pending = 0, fee = ? WHERE payhash = ? AND wallet = ?",
                (r.fee_msat, invoice.payment_hash, wallet["id"]),
            )

    return jsonify({"PAID": "TRUE", "payment_hash": invoice.payment_hash}), 200


@app.route("/api/v1/invoice/<payhash>", methods=["GET"])
def api_checkinvoice(payhash):
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 400

    with open_db() as db:
        payment = db.fetchone(
            """
            SELECT pending
            FROM apipayments
            INNER JOIN wallets AS w ON apipayments.wallet = w.id
            WHERE payhash = ?
                AND (w.adminkey = ? OR w.inkey = ?)
            """,
            (payhash, request.headers["Grpc-Metadata-macaroon"], request.headers["Grpc-Metadata-macaroon"]),
        )

        if not payment:
            return jsonify({"ERROR": "NO INVOICE"}), 404

        if not payment["pending"]:  # pending
            return jsonify({"PAID": "TRUE"}), 200

        if not WALLET.get_invoice_status(payhash).settled:
            return jsonify({"PAID": "FALSE"}), 200

        db.execute("UPDATE apipayments SET pending = 0 WHERE payhash = ?", (payhash,))
        return jsonify({"PAID": "TRUE"}), 200


@app.route("/api/v1/payment/<payhash>", methods=["GET"])
def api_checkpayment(payhash):
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 400

    with open_db() as db:
        payment = db.fetchone(
            """
            SELECT pending
            FROM apipayments
            INNER JOIN wallets AS w ON apipayments.wallet = w.id
            WHERE payhash = ?
                AND (w.adminkey = ? OR w.inkey = ?)
            """,
            (payhash, request.headers["Grpc-Metadata-macaroon"], request.headers["Grpc-Metadata-macaroon"]),
        )

        if not payment:
            return jsonify({"ERROR": "NO INVOICE"}), 404

        if not payment["pending"]:  # pending
            return jsonify({"PAID": "TRUE"}), 200

        if not WALLET.get_payment_status(payhash).settled:
            return jsonify({"PAID": "FALSE"}), 200

        db.execute("UPDATE apipayments SET pending = 0 WHERE payhash = ?", (payhash,))
        return jsonify({"PAID": "TRUE"}), 200


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


# Checks DB to see if the extensions are activated or not activated for the user
@app.route("/extensions")
def extensions():
    usr = request.args.get("usr")
    lnevents = request.args.get("lnevents")
    lnjoust = request.args.get("lnjoust")
    withdraw = request.args.get("withdraw")
    if usr:
        if not len(usr) > 20:
            return redirect(url_for("home"))

    with open_db() as db:
        user_wallets = db.fetchall("SELECT * FROM wallets WHERE user = ?", (usr,))

    with open_ext_db() as ext_db:
        user_ext = ext_db.fetchall("SELECT * FROM overview WHERE user = ?", (usr,))
        if not user_ext:
            ext_db.execute(
                """
                INSERT OR IGNORE INTO overview (user) VALUES (?)
                """,
                (usr,),
            )
            return redirect(url_for("extensions", usr=usr))

        if lnevents:
            if int(lnevents) != user_ext[0][1] and int(lnevents) < 2:
                ext_db.execute("UPDATE overview SET lnevents = ? WHERE user = ?", (int(lnevents), usr,))
                user_ext = ext_db.fetchall("SELECT * FROM overview WHERE user = ?", (usr,))
        if lnjoust:
            if int(lnjoust) != user_ext[0][2] and int(lnjoust) < 2:
                ext_db.execute("UPDATE overview SET lnjoust = ? WHERE user = ?", (int(lnjoust), usr,))
                user_ext = ext_db.fetchall("SELECT * FROM overview WHERE user = ?", (usr,))
        if withdraw:
            if int(withdraw) != user_ext[0][3] and int(withdraw) < 2:
                ext_db.execute("UPDATE overview SET withdraw = ? WHERE user = ?", (int(withdraw), usr,))
                user_ext = ext_db.fetchall("SELECT * FROM overview WHERE user = ?", (usr,))

    return render_template("extensions.html", user_wallets=user_wallets, user=usr, user_ext=user_ext)
