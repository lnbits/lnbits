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
        user_ext = db.fetchall("SELECT * FROM extensions WHERE user = ?", (usr,))
        user_ext = [v[0] for v in user_ext]

    with open_ext_db("events") as events_ext_db:
        user_ev = events_ext_db.fetchall("SELECT * FROM events WHERE usr = ?", (usr,))

        # If del is selected by user from events page, the event link is to be deleted
        evdel = request.args.get("del")
        if evdel:
            events_ext_db.execute("DELETE FROM events WHERE uni = ?", (evdel,))
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
        with open_ext_db("events") as events_ext_db:
            events_ext_db.execute("DELETE FROM events WHERE uni = ?", (unid[1],))
    else:
        uni = uuid.uuid4().hex

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
            (usr, wal, walnme, walinvkey, uni, tit, cldate, notickets, prtick)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )

        user_ev = events_ext_db.fetchall("SELECT * FROM events WHERE usr = ?", (usr,))

        if not user_ev:
            return jsonify({"ERROR": "NO WALLET USER"}), 401

    return render_template(
        "events/index.html", user_wallets=user_wallets, user=usr, user_ext=user_ext, user_ev=user_ev
    )
