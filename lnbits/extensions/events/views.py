import uuid

from flask import jsonify, render_template, request, redirect, url_for
from datetime import datetime

from lnbits.db import open_db, open_ext_db
from lnbits.extensions.events import events_ext


@events_ext.route("/")
def index():
    """Main events link page."""
    usr = request.args.get("usr")

    if usr:
        if not len(usr) > 20:
            return redirect(url_for("home"))

    # Get all the data
    with open_db() as db:
        user_wallets = db.fetchall("SELECT * FROM wallets WHERE user = ?", (usr,))
        user_ext = db.fetchall("SELECT extension FROM extensions WHERE user = ? AND active = 1", (usr,))
        user_ext = [v[0] for v in user_ext]

    with open_ext_db("events") as events_ext_db:
        user_ev = events_ext_db.fetchall("SELECT * FROM events WHERE usr = ?", (usr,))

        # If del is selected by user from events page, the event link is to be deleted
        evdel = request.args.get("del")
        if evdel:
            user_ev = events_ext_db.fetchall("SELECT * FROM events WHERE uni = ?", (evdel,))
            events_ext_db.execute("DELETE FROM events WHERE uni = ?", (evdel,))
            if user_ev[0][9] > 0:
                events_ext_db.execute("DELETE FROM eventssold WHERE uni = ?", (user_ev[0][12],))
            user_ev = events_ext_db.fetchall("SELECT * FROM events WHERE usr = ?", (usr,))
    print(user_ext)

    return render_template(
        "events/index.html", user_wallets=user_wallets, user=usr, user_ext=user_ext, user_ev=user_ev
    )

@events_ext.route("/create", methods=["GET", "POST"])
def create():
    """."""

    data = request.json
    tit = data["tit"]
    wal = data["wal"]
    cldate = data["cldate"]
    notickets = data["notickets"]
    prtick = data["prtickets"]
    usr = data["usr"]
    descr = data["descr"]
    wall = wal.split("-")

    # Form validation
    if (
        not tit.replace(" ", "").isalnum()
        or wal == ""
        or int(notickets) < 0
        or int(prtick) < 0
    ):
        return jsonify({"ERROR": "FORM ERROR"}), 401

    # If id that means its a link being edited, delete the record first
    if "id" in data:
        unid = data["id"].split("-")
        uni = unid[1]
        unireg = unid[2]
        with open_ext_db("events") as events_ext_db:
            events_ext_db.execute("DELETE FROM events WHERE uni = ?", (unid[1],))
    else:
        uni = uuid.uuid4().hex
        unireg = uuid.uuid4().hex
        
    
    with open_db() as dbb:
        user_wallets = dbb.fetchall("SELECT * FROM wallets WHERE user = ? AND id = ?", (usr, wall[1],))
    if not user_wallets:
        return jsonify({"ERROR": "NO WALLET USER"}), 401

    with open_db() as db:
        user_ext = db.fetchall("SELECT * FROM extensions WHERE user = ?", (usr,))
        user_ext = [v[0] for v in user_ext]
    
    # Add to DB
    with open_ext_db("events") as events_ext_db:
        events_ext_db.execute(
            """
            INSERT OR IGNORE INTO events
            (usr, wal, walnme, walinvkey, uni, tit, cldate, notickets, prtick, descr, unireg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usr,
                wall[1],
                user_wallets[0][1],
                user_wallets[0][4],
                uni,
                tit,
                cldate,
                notickets,
                prtick,
                descr,
                unireg,
            ),
        )

        user_ev = events_ext_db.fetchall("SELECT * FROM events WHERE usr = ?", (usr,))

        if not user_ev:
            return jsonify({"ERROR": "NO WALLET USER"}), 401

    return render_template(
        "events/index.html", user_wallets=user_wallets, user=usr, user_ext=user_ext, user_ev=user_ev
    )



@events_ext.route("/wave/<wave>/", methods=["GET", "POST"])
def wave(wave):
    """."""

    with open_ext_db("events") as events_ext_db:
        user_ev = events_ext_db.fetchall("SELECT * FROM events WHERE unireg = ?", (wave,))
        if not user_ev:
            return jsonify({"ERROR": "NO RECORD"}), 401

    return render_template(
        "events/display.html", wave=wave, nme=user_ev[0][6], descr=user_ev[0][11]
    )

@events_ext.route("/registration/<wave>", methods=["GET", "POST"])
def registration(wave):
    """."""
    with open_ext_db("events") as events_ext_db:
        user_ev = events_ext_db.fetchall("SELECT * FROM events WHERE uni = ?", (wave,))
        user_ev_sold = events_ext_db.fetchall("SELECT * FROM eventssold WHERE uni = ?  AND paid = 1", (user_ev[0][12],))
        if not user_ev:
            return jsonify({"ERROR": "NO RECORD"}), 401

    return render_template(
        "events/registration.html", user_ev=user_ev, user_ev_sold=user_ev_sold
    )

@events_ext.route("/ticket/", methods=["GET"])
def ticket():
    """."""
    thehash = request.args.get("hash")
    unireg = request.args.get("unireg")

    #Double check the payment has cleared
    with open_db() as db:
        payment = db.fetchall("SELECT * FROM apipayments WHERE payhash = ?", (thehash,))

        if not payment:
            return jsonify({"status": "ERROR", "reason":"NO RECORD OF PAYMENT"}), 400

        if payment[0][4] == 1:
            return jsonify({"status": "ERROR", "reason":"NOT PAID"}), 400
    
    #Update databases
    with open_ext_db("events") as events_ext_db:
        user_ev = events_ext_db.fetchall("SELECT * FROM events WHERE unireg = ?", (unireg,))
        updatesold = user_ev[0][9] + 1
        events_ext_db.execute("UPDATE events SET sold = ? WHERE unireg = ?", (updatesold, unireg,))
        events_ext_db.execute("UPDATE eventssold SET paid = 1 WHERE hash = ?", (thehash,))
        eventssold = events_ext_db.fetchall("SELECT * FROM eventssold WHERE hash = ?", (thehash,))
        if not eventssold:
            return jsonify({"status": "ERROR", "reason":"NO TICKET RECORD"}), 200

    return render_template(
        "events/ticket.html", name=eventssold[0][3], ticket=thehash
    )
