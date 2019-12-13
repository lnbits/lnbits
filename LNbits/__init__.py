from flask import Flask, render_template
from flask import Flask, redirect
from flask import request
from flask import jsonify
from flask import Flask, g
from random import seed
from random import random
from flask import json
import re
import os
import sqlite3
import base64
import lnurl
import requests
import time
import json
import bech32

from .db import Database, DEFAULT_PATH
from .helpers import encrypt


INVOICE_KEY = "YOUR-LNTXBOT-INVOICE-KEY"  # In the lntxbot bot on telegram type "/api"
ADMIN_KEY = "YOUR-LNTXBOT-ADMIN-KEY"
API_ENDPOINT = "YOUR-LNTXBOT-API-BASE-URL"

app = Flask(__name__)


def db_connect(db_path=DEFAULT_PATH):
    con = sqlite3.connect(db_path)
    return con


@app.route("/")
def home():

    return render_template("index.html")


@app.route("/deletewallet")
def deletewallet():
    thewal = request.args.get("wal")

    with Database() as db:
        rowss = db.fetchall("SELECT * FROM wallets WHERE hash = ?", (thewal,))

        if len(rowss) > 0:
            db.execute("UPDATE wallets SET user = ? WHERE hash = ?", (f"del{rowss[0][4]}", rowss[0][0]))
            db.execute("UPDATE wallets SET adminkey = ? WHERE hash = ?", (f"del{rowss[0][5]}", rowss[0][0]))
            db.execute("UPDATE wallets SET inkey = ? WHERE hash = ?", (f"del{rowss[0][6]}", rowss[0][0]))
            rowsss = db.fetchall("SELECT * FROM wallets WHERE user = ?", (rowss[0][4],))

            if len(rowsss) > 0:
                return render_template("deletewallet.html", theid=rowsss[0][4], thewal=rowsss[0][0])

    return render_template("index.html")


@app.route("/lnurlwallet")
def lnurlwallet():

    # put in a function
    thestr = request.args.get("lightning")
    lnurll = lnurl.decode(thestr)
    r = requests.get(url=lnurll)

    data = r.json()

    callback = data["callback"]
    maxwithdraw = data["maxWithdrawable"]
    withdraw = int(maxwithdraw / 1000)
    k1 = data["k1"]

    # get invoice
    dataj = {"amt": str(withdraw)}
    headers = {"Authorization": "Basic %s" % INVOICE_KEY}
    rr = requests.post(url=API_ENDPOINT + "/addinvoice", json=dataj, headers=headers)

    dataa = rr.json()

    # get callback

    pay_req = dataa["pay_req"]
    payment_hash = dataa["payment_hash"]

    invurl = callback + "&k1=" + k1 + "&pr=" + pay_req

    rrr = requests.get(url=invurl)
    dataaa = rrr.json()

    print(dataaa)
    print("poo")

    if dataaa["status"] == "OK":

        data = ""
        while data == "":
            r = requests.post(url=API_ENDPOINT + "/invoicestatus/" + str(payment_hash), headers=headers)
            data = r.json()
            print(r.json())

        adminkey = encrypt(payment_hash)[0:20]
        inkey = encrypt(adminkey)[0:20]
        thewal = encrypt(inkey)[0:20]
        theid = encrypt(thewal)[0:20]
        thenme = "Bitcoin LN Wallet"

        con = db_connect()
        cur = con.cursor()

        cur.execute("INSERT INTO accounts (userhash) VALUES ('" + theid + "')")
        con.commit()
        cur.close()

        con = db_connect()
        cur = con.cursor()

        adminkey = encrypt(theid)
        inkey = encrypt(adminkey)

        cur.execute(
            "INSERT INTO wallets (hash, balance, transactions, name, user, adminkey, inkey) VALUES ('"
            + thewal
            + "',',0,"
            + str(withdraw)
            + "','0','"
            + thenme
            + "','"
            + theid
            + "','"
            + adminkey
            + "','"
            + inkey
            + "')"
        )
        con.commit()
        cur.close()

        con = db_connect()
        cur = con.cursor()
        print(thewal)
        cur.execute("select * from wallets WHERE user = '" + str(theid) + "'")
        rows = cur.fetchall()
        con.commit()
        cur.close()
        return render_template(
            "lnurlwallet.html",
            len=len("1"),
            walnme=thenme,
            walbal=str(withdraw),
            theid=theid,
            thewal=thewal,
            adminkey=adminkey,
            inkey=inkey,
        )
    else:
        return render_template("index.html")


@app.route("/wallet")
def wallet():
    theid = request.args.get("usr")
    thewal = request.args.get("wal")
    thenme = request.args.get("nme")

    if not thewal:
        return render_template("index.html")

    with Database() as db:
        user_exists = len(db.fetchall("SELECT * FROM accounts WHERE userhash = ?", (theid,))) > 0

        # user exists
        # -----------

        if user_exists:
            user_wallets = db.fetchall("SELECT * FROM wallets WHERE user = ?", (theid,))

            # user has wallets
            # ----------------

            if len(user_wallets) > 0:
                wallet = db.fetchall("SELECT * FROM wallets WHERE hash = ?", (thewal,))

                if len(wallet) > 0:
                    walb = wallet[0][1].split(",")[-1]
                    return render_template(
                        "wallet.html",
                        thearr=user_wallets,
                        len=len(user_wallets),
                        walnme=wallet[0][3],
                        user=theid,
                        walbal=walb,
                        theid=theid,
                        thewal=thewal,
                        transactions=wallet[0][2],
                        adminkey=wallet[0][5],
                        inkey=wallet[0][6],
                    )

                adminkey = encrypt(thewal)
                inkey = encrypt(adminkey)

                db.execute(
                    "INSERT INTO wallets (hash, balance, transactions, name, user, adminkey, inkey) "
                    "VALUES (?, 0, 0, ?, ?, ?, ?)",
                    (thewal, thenme, theid, adminkey, inkey),
                )
                rows = db.fetchall("SELECT * FROM wallets WHERE user = ?", (theid,))

                return render_template(
                    "wallet.html",
                    thearr=rows,
                    len=len(rows),
                    walnme=thenme,
                    walbal="0",
                    theid=theid,
                    thewal=thewal,
                    adminkey=adminkey,
                    inkey=inkey,
                )

            # user has no wallets
            # -------------------

            adminkey = encrypt(theid)
            inkey = encrypt(adminkey)

            db.execute(
                "INSERT INTO wallets (hash, balance, transactions, name, user, adminkey, inkey) "
                "VALUES (?, 0, 0, ?, ?, ?, ?)",
                (thewal, thenme, theid, adminkey, inkey),
            )

            return render_template(
                "wallet.html",
                len=len("1"),
                walnme=thenme,
                walbal="0",
                theid=theid,
                thewal=thewal,
                adminkey=adminkey,
                inkey=inkey,
            )

        # user does not exist: create an account
        # --------------------------------------

        db.execute("INSERT INTO accounts (userhash) VALUES (?)", (theid,))

        adminkey = encrypt(theid)
        inkey = encrypt(adminkey)

        db.execute(
            "INSERT INTO wallets (hash, balance, transactions, name, user, adminkey, inkey) "
            "VALUES (?, 0, 0, ?, ?, ?, ?)",
            (thewal, thenme, theid, adminkey, inkey),
        )

        return render_template(
            "wallet.html",
            len=len("1"),
            walnme=thenme,
            walbal="0",
            theid=theid,
            thewal=thewal,
            adminkey=adminkey,
            inkey=inkey,
        )


# API requests
@app.route("/v1/invoices", methods=["GET", "POST"])
def api_invoices():
    if request.headers["Content-Type"] == "application/json":

        postedjson = request.json
        print(postedjson)

        if "value" in postedjson:
            if postedjson["value"].isdigit() == True:
                if "memo" in postedjson:
                    con = db_connect()
                    cur = con.cursor()

                    cur.execute(
                        "select * from wallets WHERE inkey = '" + request.headers["Grpc-Metadata-macaroon"] + "'"
                    )
                    rows = cur.fetchall()

                    if len(rows) > 0:
                        cur.close()

                        dataj = {"amt": postedjson["value"], "memo": postedjson["memo"]}
                        headers = {"Authorization": "Basic %s" % INVOICE_KEY}
                        r = requests.post(url=API_ENDPOINT + "/addinvoice", json=dataj, headers=headers)

                        data = r.json()

                        pay_req = data["pay_req"]
                        payment_hash = data["payment_hash"]

                        con = db_connect()
                        cur = con.cursor()

                        cur.execute(
                            "INSERT INTO apipayments (payhash, amount, wallet, paid, inkey, memo) VALUES ('"
                            + payment_hash
                            + "','"
                            + postedjson["value"]
                            + "','"
                            + rows[0][0]
                            + "','0','"
                            + request.headers["Grpc-Metadata-macaroon"]
                            + "','"
                            + postedjson["memo"]
                            + "')"
                        )
                        con.commit()
                        cur.close()

                        return jsonify({"pay_req": pay_req, "payment_hash": payment_hash}), 200

                    else:
                        return jsonify({"ERROR": "NO KEY"}), 200
                else:
                    return jsonify({"ERROR": "NO MEMO"}), 200
            else:
                return jsonify({"ERROR": "VALUE MUST BE A NUMMBER"}), 200
        else:
            return jsonify({"ERROR": "NO VALUE"}), 200
    else:
        return jsonify({"ERROR": "MUST BE JSON"}), 200


# API requests
@app.route("/v1/channels/transactions", methods=["GET", "POST"])
def api_transactions():
    if request.headers["Content-Type"] == "application/json":
        postedjson = request.json
        print(postedjson)
        print(postedjson["payment_request"])

        if "payment_request" in postedjson:
            con = db_connect()
            cur = con.cursor()
            print(request.headers["Grpc-Metadata-macaroon"])
            print()
            cur.execute("select * from wallets WHERE adminkey = '" + request.headers["Grpc-Metadata-macaroon"] + "'")
            rows = cur.fetchall()
            if len(rows) > 0:
                cur.close()

                s = postedjson["payment_request"]
                result = re.search("lnbc(.*)1p", s)
                tempp = result.group(1)

                alpha = ""
                num = ""

                for i in range(len(tempp)):
                    if tempp[i].isdigit():
                        num = num + tempp[i]
                    else:
                        alpha += tempp[i]
                sats = ""
                if alpha == "n":
                    sats = int(num) / 10
                elif alpha == "u":
                    sats = int(num) * 100
                elif alpha == "m":
                    sats = int(num) * 100000

                print(sats)
                print(alpha)
                print(num)

                dataj = {"invoice": postedjson["payment_request"]}
                headers = {"Authorization": "Basic %s" % ADMIN_KEY}
                r = requests.post(url=API_ENDPOINT + "/payinvoice", json=dataj, headers=headers)
                data = r.json()
                print(data)

                con = db_connect()
                cur = con.cursor()

                cur.execute(
                    "INSERT INTO apipayments (payhash, amount, wallet, paid, adminkey, memo) VALUES ('"
                    + data["decoded"]["payment_hash"]
                    + "','"
                    + str(-int(data["decoded"]["num_satoshis"]))
                    + "','"
                    + rows[0][0]
                    + "','1','"
                    + request.headers["Grpc-Metadata-macaroon"]
                    + "','"
                    + data["decoded"]["description"]
                    + "')"
                )
                con.commit()
                cur.close()

                con = db_connect()
                cur = con.cursor()
                cur.execute("select * from apipayments WHERE payhash = '" + data["decoded"]["payment_hash"] + "'")
                rowss = cur.fetchall()
                cur.close()

                data["decoded"]["num_satoshis"]

                lastamt = rows[0][1].split(",")
                newamt = int(lastamt[-1]) - int(data["decoded"]["num_satoshis"])
                updamt = rows[0][1] + "," + str(newamt)
                thetime = time.time()
                transactions = (
                    rows[0][2] + "!" + rowss[0][5] + "," + str(thetime) + "," + str(rowss[0][1]) + "," + str(newamt)
                )

                con = db_connect()
                cur = con.cursor()

                cur.execute(
                    "UPDATE wallets SET balance = '"
                    + updamt
                    + "', transactions = '"
                    + transactions
                    + "' WHERE hash = '"
                    + rows[0][0]
                    + "'"
                )
                con.commit()
                cur.close()

                return jsonify({"PAID": "TRUE"}), 200
            else:
                return jsonify({"ERROR": "BAD AUTH"}), 200
        return jsonify({"ERROR": "NO PAY REQ"}), 200

    return jsonify({"ERROR": "MUST BE JSON"}), 200


@app.route("/v1/invoice/<payhash>", methods=["GET"])
def api_checkinvoice(payhash):

    if request.headers["Content-Type"] == "application/json":

        print(request.headers["Grpc-Metadata-macaroon"])
        con = db_connect()
        cur = con.cursor()
        cur.execute("select * from apipayments WHERE payhash = '" + payhash + "'")
        rows = cur.fetchall()
        cur.close()
        print(payhash)
        if request.headers["Grpc-Metadata-macaroon"] == rows[0][4]:

            if rows[0][3] == "0":
                print(rows[0][3])
                print("did it work?")
                headers = {"Authorization": "Basic %s" % INVOICE_KEY}
                r = requests.post(url=API_ENDPOINT + "/invoicestatus/" + payhash, headers=headers)
                data = r.json()
                print(r.json())
                print("no")
                if data == "":
                    return jsonify({"PAID": "FALSE"}), 400
                else:
                    con = db_connect()
                    cur = con.cursor()

                    cur.execute("select * from wallets WHERE hash = '" + rows[0][2] + "'")

                    rowsss = cur.fetchall()
                    con.commit()
                    cur.close()

                    lastamt = rowsss[0][1].split(",")
                    newamt = int(lastamt[-1]) + int(rows[0][1])
                    updamt = rowsss[0][1] + "," + str(newamt)

                    thetime = time.time()
                    transactions = (
                        rowsss[0][2] + "!" + rows[0][5] + "," + str(thetime) + "," + str(rows[0][1]) + "," + str(newamt)
                    )

                    con = db_connect()
                    cur = con.cursor()

                    cur.execute(
                        "UPDATE wallets SET balance = '"
                        + updamt
                        + "', transactions = '"
                        + transactions
                        + "' WHERE hash = '"
                        + rows[0][2]
                        + "'"
                    )

                    con.commit()
                    cur.close()

                    con = db_connect()
                    cur = con.cursor()

                    cur.execute("UPDATE apipayments SET paid = '1' WHERE payhash = '" + payhash + "'")

                    con.commit()
                    cur.close()
                    return jsonify({"PAID": "TRUE"}), 200
            else:
                return jsonify({"PAID": "TRUE"}), 200
        else:
            return jsonify({"ERROR": "WRONG KEY"}), 400

    else:
        return jsonify({"ERROR": "NEEDS TO BE JSON"}), 400


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
