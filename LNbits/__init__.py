import lnurl
import uuid
import os
import requests

from flask import Flask, jsonify, render_template, request, redirect, url_for

from . import bolt11
from .db import Database
from .settings import DATABASE_PATH, LNBITS_PATH, WALLET, DEFAULT_USER_WALLET_NAME


app = Flask(__name__)


def db_connect(db_path=DATABASE_PATH):
    import sqlite3

    con = sqlite3.connect(db_path)
    return con


@app.before_first_request
def init():
    with Database() as db:
        with open(os.path.join(LNBITS_PATH, "data", "schema.sql")) as schemafile:
            for stmt in schemafile.read().split("\n\n"):
                db.execute(stmt, [])


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/deletewallet")
def deletewallet():
    theid = request.args.get("usr")
    thewal = request.args.get("wal")

    with Database() as db:
        db.execute(
            """
            UPDATE wallets AS w SET
              user = 'del:' || w.user,
              adminkey = 'del:' || w.adminkey,
              inkey = 'del:' || w.inkey
            WHERE id = ? AND user = ?
        """,
            (thewal, theid),
        )

        next_wallet = db.fetchone("SELECT hash FROM wallets WHERE user = ?", (theid,))
        if next_wallet:
            return redirect(url_for("wallet", usr=theid, wal=next_wallet[0]))

    return render_template("index.html")


@app.route("/lnurlwallet")
def lnurlwallet():
    withdraw_res = lnurl.handle(request.args.get("lightning"))
    invoice = WALLET.create_invoice(withdraw_res.max_sats).json()
    payment_hash = invoice["payment_hash"]

    r = requests.get(
        withdraw_res.callback.base,
        params={**withdraw_res.callback.query_params, **{"k1": withdraw_res.k1, "pr": invoice["pay_req"]}},
    )
    data = r.json()

    if data["status"] != "OK":
        """TODO: show some kind of error?"""
        return render_template("index.html")

    data = ""
    while data == "":
        r = WALLET.get_invoice_status(payment_hash)
        data = r.json()

    with Database() as db:
        adminkey = uuid.uuid4().hex
        inkey = uuid.uuid4().hex
        thewal = uuid.uuid4().hex
        theid = uuid.uuid4().hex
        thenme = DEFAULT_USER_WALLET_NAME

        db.execute("INSERT INTO accounts (id) VALUES (?)", (theid,))
        db.execute(
            "INSERT INTO wallets (id, name, user, adminkey, inkey) VALUES (?, ?, ?, ?, ?)",
            (thewal, thenme, theid, adminkey, inkey),
        )

        return redirect(url_for("wallet", usr=theid, wal=thewal))


@app.route("/wallet")
def wallet():
    usr = request.args.get("usr")
    wallet_id = request.args.get("wal")
    wallet_name = request.args.get("nme") or DEFAULT_USER_WALLET_NAME

    # just usr: return a the first user wallet or create one if none found
    # usr and wallet_id: return that wallet or create it if it doesn't exist
    # usr, wallet_id and wallet_name: same as above, but use the specified name
    # usr and wallet_name: generate a wallet_id and create
    # wallet_id and wallet_name: create a user, then move an existing wallet or create
    # just wallet_name: create a user, then generate a wallet_id and create
    # nothing: create everything

    with Database() as db:
        # ensure this user exists
        # -------------------------------

        if not usr:
            usr = uuid.uuid4().hex
            return redirect(url_for("wallet", usr=usr, wal=wallet_id, nme=wallet_name))

        db.execute(
            """
          INSERT INTO accounts (id) VALUES (?)
          ON CONFLICT (id) DO NOTHING
        """,
            (usr,),
        )

        user_wallets = db.fetchall("SELECT * FROM wallets WHERE user = ?", (usr,))

        if not wallet_id:
            # if not given, fetch the first wallet from this user or create
            # -------------------------------------------------------------
            if user_wallets:
                wallet_id = user_wallets[0]["id"]
            else:
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
          INSERT INTO wallets (id, name, user, adminkey, inkey)
          VALUES (?, ?, ?, ?, ?)
          ON CONFLICT (id) DO UPDATE SET user = ?
        """,
            (wallet_id, wallet_name, usr, uuid.uuid4().hex, uuid.uuid4().hex, usr),
        )

        # finally, get the wallet with balance and transactions
        # -----------------------------------------------------

        wallet = db.fetchone(
            """
          SELECT
            coalesce(
              (SELECT balance/1000 FROM balances WHERE wallet = wallets.id),
              0
            ) AS balance,
            name,
            adminkey,
            inkey
          FROM wallets
          WHERE user = ? AND id = ?
        """,
            (usr, wallet_id),
        )

        transactions = []

        return render_template(
            "wallet.html", user_wallets=user_wallets, wallet=wallet, user=usr, transactions=transactions,
        )


@app.route("/v1/invoices", methods=["GET", "POST"])
def api_invoices():
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 400

    postedjson = request.json

    if "value" not in postedjson:
        return jsonify({"ERROR": "NO VALUE"}), 400

    if not postedjson["value"].isdigit():
        return jsonify({"ERROR": "VALUE MUST BE A NUMBER"}), 400

    if int(postedjson["value"]) < 0:
        return jsonify({"ERROR": "AMOUNTLESS INVOICES NOT SUPPORTED"}), 400

    if "memo" not in postedjson:
        return jsonify({"ERROR": "NO MEMO"}), 400

    with Database() as db:
        wallet = db.fetchone(
            "SELECT id FROM wallets WHERE inkey = ? OR adminkey = ?",
            (request.headers["Grpc-Metadata-macaroon"], request.headers["Grpc-Metadata-macaroon"],),
        )

        if not wallet:
            return jsonify({"ERROR": "NO KEY"}), 200

        r = WALLET.create_invoice(postedjson["value"], postedjson["memo"])
        data = r.json()

        pay_req = data["pay_req"]
        payment_hash = data["payment_hash"]
        amount_msat = int(postedjson["value"]) * 1000

        db.execute(
            "INSERT INTO apipayments (payhash, amount, wallet, pending, memo) VALUES (?, ?, ?, true, ?)",
            (payment_hash, amount_msat, wallet["id"], postedjson["memo"],),
        )

    return jsonify({"pay_req": pay_req, "payment_hash": payment_hash}), 200


@app.route("/v1/channels/transactions", methods=["GET", "POST"])
def api_transactions():
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 200

    data = request.json

    if "payment_request" not in data:
        return jsonify({"ERROR": "NO PAY REQ"}), 200

    with Database() as db:
        wallet = db.fetchone("SELECT id FROM wallets WHERE adminkey = ?", (request.headers["Grpc-Metadata-macaroon"],))

        if not wallet:
            return jsonify({"ERROR": "BAD AUTH"}), 200

        # decode the invoice
        invoice = bolt11.decode(data["payment_request"])
        if invoice.amount_msat == 0:
            return jsonify({"ERROR": "AMOUNTLESS INVOICES NOT SUPPORTED"}), 400

        # insert the payment
        db.execute(
            "INSERT INTO apipayments (payhash, amount, fee, wallet, pending, memo) VALUES (?, ?, ?, ?, true, ?)",
            (
                invoice.payment_hash,
                -int(invoice.amount_msat),
                -int(invoice.amount_msat * 0.01),
                wallet["id"],
                invoice.description,
            ),
        )

        # check balance
        balance = db.fetchone("SELECT balance/1000 FROM balances WHERE wallet = ?", (wallet["id"],))[0]
        if balance < 0:
            return jsonify({"ERROR": "INSUFFICIENT BALANCE"}), 403

        # actually send the payment
        r = WALLET.pay_invoice(data["payment_request"])

        if not r.ok:
            return jsonify({"ERROR": "UNEXPECTED PAYMENT ERROR"}), 500

        data = r.json()
        if r.ok and "error" in data:
            # payment didn't went through, delete it here
            # (these guarantees specific to lntxbot)
            db.execute("DELETE FROM apipayments WHERE payhash = ?", (invoice.payment_hash,))
            return jsonify({"PAID": "FALSE"}), 200

        # payment went through, not pending anymore, save actual fees
        db.execute(
            "UPDATE apipayments SET pending = false, fee = ? WHERE payhash = ?",
            (data["fee_msat"], invoice.payment_hash,),
        )

    return jsonify({"PAID": "TRUE"}), 200


@app.route("/v1/invoice/<payhash>", methods=["GET"])
def api_checkinvoice(payhash):
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 200

    with Database() as db:
        payment = db.fetchone(
            """
          SELECT pending FROM apipayments
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

        r = WALLET.get_invoice_status(payhash)
        if not r.ok:
            return jsonify({"PAID": "FALSE"}), 400

        data = r.json()
        if "preimage" not in data or not data["preimage"]:
            return jsonify({"PAID": "FALSE"}), 400

        db.execute("UPDATE apipayments SET pending = false WHERE payhash = ?", (payhash,))
        return jsonify({"PAID": "TRUE"}), 200
