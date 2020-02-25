import uuid
import json
import requests

from flask import jsonify, render_template, request, redirect, url_for
from lnbits.db import open_db, open_ext_db
from lnbits.extensions.tpos import tpos_ext

#add your endpoints here

@tpos_ext.route("/")
def index():
    """Try to add descriptions for others."""
    usr = request.args.get("usr")
    nme = request.args.get("nme")

    if usr:
        if not len(usr) > 20:
            return redirect(url_for("home"))

    # Get all the data
    with open_db() as db:
        user_wallets = db.fetchall("SELECT * FROM wallets WHERE user = ?", (usr,))
        user_ext = db.fetchall("SELECT extension FROM extensions WHERE user = ? AND active = 1", (usr,))
        user_ext = [v[0] for v in user_ext]
    
    if nme:
        uni = uuid.uuid4().hex
        with open_ext_db("tpos") as pos_ext_db:
            pos_ext_db.execute(
                """
                INSERT OR IGNORE INTO tpos
                (nme, uni, usr, invkey)
                VALUES (?, ?, ?, ?)
                """,
                (
                    nme,
                    uni,
                    usr,
                    user_wallets[0][3],

                ),
            )
    with open_ext_db("tpos") as pos_ext_dbb:
        user_fau = pos_ext_dbb.fetchall("SELECT * FROM tpos WHERE usr = ?", (usr,))

    return render_template(
        "tpos/index.html", user_wallets=user_wallets, user_ext=user_ext, usr=usr, user_fau=user_fau
    )

@tpos_ext.route("/tpos")
def tpos():
    """Try to add descriptions for others."""
    pos = request.args.get("pos")
    exc = request.args.get("exc")

    with open_ext_db("tpos") as pos_ext_dbb:
        user_fau = pos_ext_dbb.fetchall("SELECT * FROM tpos WHERE uni = ?", (pos,))
    if not user_fau:
        return jsonify({"status": "ERROR", "reason":"NO POS"}), 400

    return render_template(
        "tpos/tpos.html", pos=pos, exchange=exc
    )
