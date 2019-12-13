import lnurl
import requests
import time

from flask import Flask, jsonify, render_template, request

from .db import Database, DEFAULT_PATH
from .helpers import encrypt


INVOICE_KEY = "YOUR-LNTXBOT-INVOICE-KEY"  # In the lntxbot bot on telegram type "/api"
ADMIN_KEY = "YOUR-LNTXBOT-ADMIN-KEY"
API_ENDPOINT = "YOUR-LNTXBOT-API-BASE-URL"

app = Flask(__name__)


def db_connect(db_path=DEFAULT_PATH):
    import sqlite3
    con = sqlite3.connect(db_path)
    return con


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/deletewallet")
def deletewallet():
    thewal = request.args.get("wal")

    with Database() as db:
        wallets = db.fetchall("SELECT * FROM wallets WHERE hash = ?", (thewal,))

        if wallets:
            db.execute("UPDATE wallets SET user = ? WHERE hash = ?", (f"del{wallets[0][4]}", wallets[0][0]))
            db.execute("UPDATE wallets SET adminkey = ? WHERE hash = ?", (f"del{wallets[0][5]}", wallets[0][0]))
            db.execute("UPDATE wallets SET inkey = ? WHERE hash = ?", (f"del{wallets[0][6]}", wallets[0][0]))
            user_wallets = db.fetchall("SELECT * FROM wallets WHERE user = ?", (wallets[0][4],))

            if user_wallets:
                return render_template("deletewallet.html", theid=user_wallets[0][4], thewal=user_wallets[0][0])

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

            if user_wallets:
                wallet = db.fetchall("SELECT * FROM wallets WHERE hash = ?", (thewal,))

                if wallet:
                    walb = str(wallet[0][1]).split(",")[-1]
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


@app.route("/v1/invoices", methods=["GET", "POST"])
def api_invoices():
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 200

    postedjson = request.json

    if "value" not in postedjson:
        return jsonify({"ERROR": "NO VALUE"}), 200

    if not postedjson["value"].isdigit():
        return jsonify({"ERROR": "VALUE MUST BE A NUMMBER"}), 200

    if "memo" not in postedjson:
        return jsonify({"ERROR": "NO MEMO"}), 200

    with Database() as db:
        rows = db.fetchall("SELECT * FROM wallets WHERE inkey = ?", (request.headers["Grpc-Metadata-macaroon"],))

        if not rows:
            return jsonify({"ERROR": "NO KEY"}), 200

        dataj = {"amt": postedjson["value"], "memo": postedjson["memo"]}
        headers = {"Authorization": f"Basic {INVOICE_KEY}"}
        r = requests.post(url=f"{API_ENDPOINT}/addinvoice", json=dataj, headers=headers)
        data = r.json()

        pay_req = data["pay_req"]
        payment_hash = data["payment_hash"]

        db.execute(
            "INSERT INTO apipayments (payhash, amount, wallet, paid, inkey, memo) VALUES (?, ?, ?, 0, ?, ?)",
            (
                payment_hash,
                postedjson["value"],
                rows[0][0],
                request.headers["Grpc-Metadata-macaroon"],
                postedjson["memo"],
            ),
        )

    return jsonify({"pay_req": pay_req, "payment_hash": payment_hash}), 200


@app.route("/v1/channels/transactions", methods=["GET", "POST"])
def api_transactions():
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 200

    postedjson = request.json

    if "payment_request" not in postedjson:
        return jsonify({"ERROR": "NO PAY REQ"}), 200

    with Database() as db:
        wallets = db.fetchall("SELECT * FROM wallets WHERE adminkey = ?", (request.headers["Grpc-Metadata-macaroon"],))

        if not wallets:
            return jsonify({"ERROR": "BAD AUTH"}), 200

        # TODO: check this unused code
        # move sats calculation to a helper
        # ---------------------------------
        """
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
        """
        # ---------------------------------

        dataj = {"invoice": postedjson["payment_request"]}
        headers = {"Authorization": f"Basic {ADMIN_KEY}"}
        r = requests.post(url=f"{API_ENDPOINT}/payinvoice", json=dataj, headers=headers)
        data = r.json()

        db.execute(
            "INSERT INTO apipayments (payhash, amount, wallet, paid, adminkey, memo) VALUES (?, ?, ?, 1, ?, ?)'",
            (
                data["decoded"]["payment_hash"],
                str(-int(data["decoded"]["num_satoshis"])),
                wallets[0][0],
                request.headers["Grpc-Metadata-macaroon"],
                data["decoded"]["description"],
            ),
        )

        payment = db.fetchall("SELECT * FROM apipayments WHERE payhash = ?", (data["decoded"]["payment_hash"],))[0]

        lastamt = str(wallets[0][1]).split(",")
        newamt = int(lastamt[-1]) - int(data["decoded"]["num_satoshis"])
        updamt = wallets[0][1] + "," + str(newamt)
        transactions = f"{wallets[0][2]}!{payment[5]},{time.time()},{payment[1]},{newamt}"

        db.execute(
            "UPDATE wallets SET balance = ?, transactions = ? WHERE hash = ?", (updamt, transactions, wallets[0][0])
        )

    return jsonify({"PAID": "TRUE"}), 200


@app.route("/v1/invoice/<payhash>", methods=["GET"])
def api_checkinvoice(payhash):
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 200

    with Database() as db:
        payment = db.fetchall("SELECT * FROM apipayments WHERE payhash = ?", (payhash,))[0]

        if request.headers["Grpc-Metadata-macaroon"] != payment[4]:
            return jsonify({"ERROR": "WRONG KEY"}), 400

        if payment[3] != "0":
            return jsonify({"PAID": "TRUE"}), 200

        headers = {"Authorization": f"Basic {INVOICE_KEY}"}
        r = requests.post(url=f"{API_ENDPOINT}/invoicestatus/{payhash}", headers=headers)
        data = r.json()

        if data == "":
            return jsonify({"PAID": "FALSE"}), 400

        wallet = db.fetchall("SELECT * FROM wallets WHERE hash = ?", (payment[2],))[0]

        lastamt = wallet[1].split(",")
        newamt = int(lastamt[-1]) + int(payment[1])
        updamt = wallet[1] + "," + str(newamt)
        transactions = f"{wallet[2]}!{payment[5]},{time.time()},{payment[1]},{newamt}"

        db.execute(
            "UPDATE wallets SET balance = ?, transactions = ? WHERE hash = ?", (updamt, transactions, payment[2])
        )
        db.execute("UPDATE apipayments SET paid = '1' WHERE payhash = ?", (payhash,))

    return jsonify({"PAID": "TRUE"}), 200
