import uuid

from flask import jsonify, render_template, request, redirect, url_for
from lnurl import encode as lnurl_encode
from datetime import datetime

from lnbits.db import open_db, open_ext_db
from lnbits.extensions.withdraw import withdraw_ext


@withdraw_ext.route("/")
def index():
    """Main withdraw link page."""

    usr = request.args.get("usr")

    if usr:
        if not len(usr) > 20:
            return redirect(url_for("home"))

    # Get all the data
    with open_db() as db:
        user_wallets = db.fetchall("SELECT * FROM wallets WHERE user = ?", (usr,))
        user_ext = db.fetchall("SELECT * FROM extensions WHERE user = ?", (usr,))
        user_ext = [v[0] for v in user_ext]

    with open_ext_db("withdraw") as withdraw_ext_db:
        user_fau = withdraw_ext_db.fetchall("SELECT * FROM withdraws WHERE usr = ?", (usr,))

        # If del is selected by user from withdraw page, the withdraw link is to be deleted
        faudel = request.args.get("del")
        if faudel:
            withdraw_ext_db.execute("DELETE FROM withdraws WHERE uni = ?", (faudel,))
            user_fau = withdraw_ext_db.fetchall("SELECT * FROM withdraws WHERE usr = ?", (usr,))

    return render_template(
        "withdraw/index.html", user_wallets=user_wallets, user=usr, user_ext=user_ext, user_fau=user_fau
    )


@withdraw_ext.route("/create", methods=["GET", "POST"])
def create():
    """."""

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

    # Form validation
    if (
        int(amt) < 0
        or not tit.replace(" ", "").isalnum()
        or wal == ""
        or int(minamt) < 0
        or int(maxamt) < 0
        or int(minamt) > int(maxamt)
        or int(tme) < 0
    ):
        return jsonify({"ERROR": "FORM ERROR"}), 401

    # If id that means its a link being edited, delet the record first
    if "id" in data:
        unid = data["id"].split("-")
        uni = unid[1]
        with open_ext_db("withdraw") as withdraw_ext_db:
            withdraw_ext_db.execute("DELETE FROM withdraws WHERE uni = ?", (unid[1],))
    else:
        uni = uuid.uuid4().hex

    # Randomiser for random QR option
    rand = ""
    if uniq > 0:
        for x in range(0, int(amt)):
            rand += uuid.uuid4().hex[0:5] + ","
    else:
        rand = uuid.uuid4().hex[0:5] + ","

    with open_db() as dbb:
        user_wallets = dbb.fetchall("SELECT * FROM wallets WHERE user = ? AND id = ?", (usr, wall[1],))
    if not user_wallets:
        return jsonify({"ERROR": "NO WALLET USER"}), 401

    # Get time
    dt = datetime.now()
    seconds = dt.timestamp()

    with open_db() as db:
        user_ext = db.fetchall("SELECT * FROM extensions WHERE user = ?", (usr,))
        user_ext = [v[0] for v in user_ext]

    # Add to DB
    with open_ext_db("withdraw") as withdraw_ext_db:
        withdraw_ext_db.execute(
            """
            INSERT OR IGNORE INTO withdraws
            (usr, wal, walnme, adm, uni, tit, maxamt, minamt, spent, inc, tme, uniq, withdrawals, tmestmp, rand)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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

        user_fau = withdraw_ext_db.fetchall("SELECT * FROM withdraws WHERE usr = ?", (usr,))

        if not user_fau:
            return jsonify({"ERROR": "NO WALLET USER"}), 401

    return render_template(
        "withdraw/index.html", user_wallets=user_wallets, user=usr, user_ext=user_ext, user_fau=user_fau
    )


@withdraw_ext.route("/display", methods=["GET", "POST"])
def display():
    """Simple shareable link."""
    fauid = request.args.get("id")

    with open_ext_db("withdraw") as withdraw_ext_db:
        user_fau = withdraw_ext_db.fetchall("SELECT * FROM withdraws WHERE uni = ?", (fauid,))

    return render_template("withdraw/display.html", user_fau=user_fau,)


@withdraw_ext.route("/print/<urlstr>/", methods=["GET", "POST"])
def print_qr(urlstr):
    """Simple printable page of links."""
    fauid = request.args.get("id")

    with open_ext_db("withdraw") as withdraw_ext_db:
        user_fau = withdraw_ext_db.fetchall("SELECT * FROM withdraws WHERE uni = ?", (fauid,))
        randar = user_fau[0][15].split(",")
        randar = randar[:-1]
        lnurlar = []

        for d in range(len(randar)):
            url = url_for("withdraw.api_lnurlfetch", _external=True, urlstr=urlstr, parstr=fauid, rand=randar[d])
            lnurlar.append(lnurl_encode(url.replace("http://", "https://")))

    return render_template("withdraw/print.html", lnurlar=lnurlar, user_fau=user_fau[0],)
