import uuid
import os
import json
import requests
import re

from flask import Flask, jsonify, render_template, request, redirect, url_for
from lnurl import Lnurl, LnurlWithdrawResponse, encode
from datetime import datetime

from . import bolt11
from .db import Database, ExtDatabase, FauDatabase
from .helpers import megajson
from .settings import LNBITS_PATH, WALLET, DEFAULT_USER_WALLET_NAME, FEE_RESERVE


app = Flask(__name__)
app.jinja_env.filters["megajson"] = megajson


@app.before_first_request
def init():
    with Database() as db:
        with open(os.path.join(LNBITS_PATH, "data", "schema.sql")) as schemafile:
            for stmt in schemafile.read().split(";\n\n"):
                db.execute(stmt, [])

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/deletewallet")
def deletewallet():
    user_id = request.args.get("usr")
    wallet_id = request.args.get("wal")

    with Database() as db:
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

    with Database() as db:
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

    with Database() as db:
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


@app.route("/v1/invoices", methods=["GET", "POST"])
def api_invoices():
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 400

    postedjson = request.json

    #Form validation 
    if int(postedjson["value"]) < 0 or not postedjson["memo"].replace(' ','').isalnum():
        return jsonify({"ERROR": "FORM ERROR"}), 401

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

        r, pay_hash, pay_req = WALLET.create_invoice(postedjson["value"], postedjson["memo"])

        if not r.ok or "error" in r.json():
            return jsonify({"ERROR": "UNEXPECTED BACKEND ERROR"}), 500

        amount_msat = int(postedjson["value"]) * 1000

        db.execute(
            "INSERT INTO apipayments (payhash, amount, wallet, pending, memo) VALUES (?, ?, ?, 1, ?)",
            (pay_hash, amount_msat, wallet["id"], postedjson["memo"],),
        )

    return jsonify({"pay_req": pay_req, "payment_hash": pay_hash}), 200


@app.route("/v1/channels/transactions", methods=["GET", "POST"])
def api_transactions():

    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 400

    data = request.json

    print(data)
    if "payment_request" not in data:
        return jsonify({"ERROR": "NO PAY REQ"}), 400

    with Database() as db:
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


@app.route("/v1/invoice/<payhash>", methods=["GET"])
def api_checkinvoice(payhash):
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 400

    with Database() as db:
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


@app.route("/v1/payment/<payhash>", methods=["GET"])
def api_checkpayment(payhash):
    if request.headers["Content-Type"] != "application/json":
        return jsonify({"ERROR": "MUST BE JSON"}), 400

    with Database() as db:
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


@app.route("/v1/checkpending", methods=["POST"])
def api_checkpending():
    with Database() as db:
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




###########EXTENSIONS STUFF - ADD TO LNFAUCET FOLDER IF POSS

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
   
    with Database() as db:

        user_wallets = db.fetchall("SELECT * FROM wallets WHERE user = ?", (usr,))

    with ExtDatabase() as Extdd:
        user_ext = Extdd.fetchall("SELECT * FROM overview WHERE user = ?", (usr,))
        if not user_ext:
            Extdd.execute(
                """
                INSERT OR IGNORE INTO overview (user) VALUES (?)
                """,
                (usr,),
            )
            return redirect(url_for("extensions", usr=usr))

        if lnevents:
            if int(lnevents) != user_ext[0][1] and int(lnevents) < 2:
                Extdd.execute("UPDATE overview SET lnevents = ? WHERE user = ?", (int(lnevents),usr,))
                user_ext = Extdd.fetchall("SELECT * FROM overview WHERE user = ?", (usr,))
        if lnjoust:
            if int(lnjoust) != user_ext[0][2] and int(lnjoust) < 2:
                Extdd.execute("UPDATE overview SET lnjoust = ? WHERE user = ?", (int(lnjoust),usr,))
                user_ext = Extdd.fetchall("SELECT * FROM overview WHERE user = ?", (usr,))
        if withdraw:
            if int(withdraw) != user_ext[0][3] and int(withdraw) < 2:
                Extdd.execute("UPDATE overview SET withdraw = ? WHERE user = ?", (int(withdraw),usr,))
                user_ext = Extdd.fetchall("SELECT * FROM overview WHERE user = ?", (usr,))

    return render_template(
            "extensions.html", user_wallets=user_wallets, user=usr, user_ext=user_ext
    )


# Main withdraw link page
@app.route("/withdraw")
def withdraw():
    usr = request.args.get("usr")
    fauc = request.args.get("fauc")

    if usr:
        if not len(usr) > 20:
            return redirect(url_for("home"))
   
   #Get all the data
    with Database() as db:
        user_wallets = db.fetchall("SELECT * FROM wallets WHERE user = ?", (usr,))

    with ExtDatabase() as Extdd:
        user_ext = Extdd.fetchall("SELECT * FROM overview WHERE user = ?", (usr,))

    with FauDatabase() as Faudb:
        user_fau = Faudb.fetchall("SELECT * FROM withdraws WHERE usr = ?", (usr,))

    #If del is selected by user from withdraw page, the withdraw link is to be deleted
        faudel = request.args.get("del")
        if faudel:
            Faudb.execute("DELETE FROM withdraws WHERE uni = ?", (faudel,))
            user_fau = Faudb.fetchall("SELECT * FROM withdraws WHERE usr = ?", (usr,))

    return render_template(
        "withdraw.html", user_wallets=user_wallets, user=usr, user_ext=user_ext, user_fau=user_fau
    )


#Returns encoded LNURL if web url and parameter gieven
@app.route("/v1/lnurlencode/<urlstr>/<parstr>", methods=["GET"])
def api_lnurlencode(urlstr, parstr):

    if not urlstr:
        return jsonify({"STATUS": "FALSE"}), 200

    with FauDatabase() as Faudb:
        user_fau = Faudb.fetchall("SELECT * FROM withdraws WHERE uni = ?", (parstr,))
        randar = user_fau[0][15].split(",")
       # randar = randar[:-1]
        print(int(user_fau[0][10])-1)
        #If "Unique links" selected get correct rand, if not there is only one rand
        if user_fau[0][12] > 0:
            rand = randar[user_fau[0][10]-2]
            print(rand)
        else:
            rand = randar[0]

    lnurlstr = encode( "https://" + urlstr + "/v1/lnurlfetch/" + urlstr + "/" + parstr + "/" + rand)

    return jsonify({"STATUS": "TRUE", "LNURL": lnurlstr}), 200


#Returns LNURL json
@app.route("/v1/lnurlfetch/<urlstr>/<parstr>/<rand>", methods=["GET"])
def api_lnurlfetch(parstr, urlstr, rand):

    if not parstr:
        return jsonify({"STATUS": "FALSE", "ERROR": "NO WALL ID"}), 200

    if not urlstr:

        return jsonify({"STATUS": "FALSE", "ERROR": "NO URL"}), 200

    with FauDatabase() as Faudb:

        user_fau = Faudb.fetchall("SELECT * FROM withdraws WHERE uni = ?", (parstr,))
        print(user_fau[0][0])

        k1str = uuid.uuid4().hex
    
        Faudb.execute("UPDATE withdraws SET withdrawals = ? WHERE uni = ?", (k1str ,parstr,))
       
    res = LnurlWithdrawResponse(
        callback='https://' + urlstr + '/v1/lnurlwithdraw/' + rand + '/',
        k1=k1str,
        min_withdrawable=user_fau[0][8]*1000,
        max_withdrawable=user_fau[0][7]*1000,
        default_description="LNURL withdraw",
    )
    print("res")
    return res.json(), 200



#Pays invoice if passed k1 invoice and rand
@app.route("/v1/lnurlwithdraw/<rand>/", methods=["GET"])
def api_lnurlwithdraw(rand):
    k1 = request.args.get("k1")
    pr = request.args.get("pr")
    print(rand)

    
    if not k1:
        return jsonify({"STATUS": "FALSE", "ERROR": "NO k1"}), 200

    if not pr:
        return jsonify({"STATUS": "FALSE", "ERROR": "NO PR"}), 200

    with FauDatabase() as Faudb:
        user_fau = Faudb.fetchall("SELECT * FROM withdraws WHERE withdrawals = ?", (k1,))

        if not user_fau:
            return jsonify({"status":"ERROR", "reason":"NO AUTH"}), 400

        if user_fau[0][10] <1:
            return jsonify({"status":"ERROR", "reason":"withdraw SPENT"}), 400

        # Check withdraw time
        dt = datetime.now()  
        seconds = dt.timestamp()
        secspast = seconds - user_fau[0][14]
        print(secspast)

        if secspast < user_fau[0][11]:
            return jsonify({"status":"ERROR", "reason":"WAIT " + str(int(user_fau[0][11] - secspast)) + "s"}), 400

        randar = user_fau[0][15].split(",")
        if rand not in randar:
            return jsonify({"status":"ERROR", "reason":"BAD AUTH"}), 400
        if len(randar) > 2:
            randar.remove(rand)
        randstr = ','.join(randar)
       
        print(randstr)
       
        # Update time and increments 
        upinc = (int(user_fau[0][10]) - 1)
        Faudb.execute("UPDATE withdraws SET inc = ?, rand = ?, tmestmp = ? WHERE withdrawals = ?", (upinc, randstr, seconds, k1,))

    header = {'Content-Type': 'application/json','Grpc-Metadata-macaroon':str(user_fau[0][4])} 

    data = {'payment_request': pr} 
  
    r = requests.post(url = "https://zapped.ngrok.io/v1/channels/transactions", headers=header, data=json.dumps(data)) 

    r_json=r.json()
    if "ERROR" in r_json:
        return jsonify({"status":"ERROR", "reason":r_json["ERROR"]}), 400

    with FauDatabase() as Faudb:
        user_fau = Faudb.fetchall("SELECT * FROM withdraws WHERE withdrawals = ?", (k1,))

    return jsonify({"status":"OK"}), 200



@app.route("/withdrawmaker", methods=["GET", "POST"])
def withdrawmaker():
    data = request.json
    amt = data["amt"]
    tit = data["tit"]
    wal = data["wal"]
    minamt = data["minamt"]
    maxamt = data["maxamt"]
    tme = data["tme"]
    uniq = data["uniq"]
    usr = data["usr"]
    wall = wal.split("-")

    #Form validation 
    if int(amt) < 0 or not tit.replace(' ','').isalnum() or wal == "" or int(minamt) < 0 or int(maxamt) < 0 or int(minamt) > int(maxamt) or int(tme) < 0:
        return jsonify({"ERROR": "FORM ERROR"}), 401
   
    #If id that means its a link being edited, delet the record first
    if "id" in data:
        unid = data["id"].split("-")
        uni = unid[1]
        print(data["id"])
        print(uni)
        with FauDatabase() as Faudb:
            Faudb.execute("DELETE FROM withdraws WHERE uni = ?", (unid[1],))
    else:
        uni = uuid.uuid4().hex
    
    # Randomiser for random QR option
    rand = ""
    if uniq > 0:
        for x in range(0,int(amt)):
            rand += uuid.uuid4().hex[0:5] + ","
    else:
        rand = uuid.uuid4().hex[0:5] + ","

    with Database() as dbb:
        user_wallets = dbb.fetchall("SELECT * FROM wallets WHERE user = ? AND id = ?", (usr,wall[1],))
    if not user_wallets:
            return jsonify({"ERROR": "NO WALLET USER"}), 401

    # Get time
    dt = datetime.now()  
    seconds = dt.timestamp()
    print(seconds)

    #Add to DB
    with FauDatabase() as db:
        db.execute(
            "INSERT OR IGNORE INTO withdraws (usr, wal, walnme, adm, uni, tit, maxamt, minamt, spent, inc, tme, uniq, withdrawals, tmestmp, rand) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                usr, 
                wall[1], 
                user_wallets[0][1],
                user_wallets[0][3], 
                uni, 
                tit, 
                maxamt, 
                minamt, 
                0, 
                amt, 
                tme, 
                uniq,  
                0,
                seconds,
                rand,
            ),
        )
        
   #Get updated records
    with ExtDatabase() as Extdd:
        user_ext = Extdd.fetchall("SELECT * FROM overview WHERE user = ?", (usr,))
        if not user_ext:
            return jsonify({"ERROR": "NO WALLET USER"}), 401
            
    with FauDatabase() as Faudb:
        user_fau = Faudb.fetchall("SELECT * FROM withdraws WHERE usr = ?", (usr,))
        if not user_fau:
            return jsonify({"ERROR": "NO WALLET USER"}), 401
            

    return render_template(
        "withdraw.html", user_wallets=user_wallets, user=usr, user_ext=user_ext, user_fau=user_fau
    )
    

#Simple shareable link
@app.route("/displaywithdraw", methods=["GET", "POST"])
def displaywithdraw():
    fauid = request.args.get("id")

    with FauDatabase() as Faudb:
        user_fau = Faudb.fetchall("SELECT * FROM withdraws WHERE uni = ?", (fauid,))

    return render_template(
        "displaywithdraw.html", user_fau=user_fau,
    )

#Simple printable page of links
@app.route("/printwithdraw/<urlstr>/", methods=["GET", "POST"])
def printwithdraw(urlstr):
    fauid = request.args.get("id")

    with FauDatabase() as Faudb:
        user_fau = Faudb.fetchall("SELECT * FROM withdraws WHERE uni = ?", (fauid,))
        randar = user_fau[0][15].split(",")
        randar = randar[:-1]
        lnurlar = []
        print(len(randar))
        for d in range(len(randar)):
            lnurlar.append( encode("https://"+ urlstr +"/v1/lnurlfetch/" + urlstr + "/" + fauid + "/" + randar[d]))
  
    return render_template(
        "printwithdraws.html", lnurlar=lnurlar, user_fau=user_fau[0],
    ) 
