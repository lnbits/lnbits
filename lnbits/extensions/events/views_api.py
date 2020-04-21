import uuid
import json
import requests

from flask import jsonify, request, url_for
from datetime import datetime

from lnbits.db import open_db, open_ext_db
from lnbits.extensions.events import events_ext

@events_ext.route("/api/v1/getticket/", methods=["GET","POST"])
def api_getticket():
    """."""

    data = request.json
    unireg = data["unireg"]
    name = data["name"]
    email = request.args.get("ema")

    with open_ext_db("events") as events_ext_db:
        user_ev = events_ext_db.fetchall("SELECT * FROM events WHERE unireg = ?", (unireg,))


        header = {"Content-Type": "application/json", "X-Api-Key": user_ev[0][4]}
        data = {"value": str(user_ev[0][10]), "memo": user_ev[0][6]}
        print(url_for("api_invoices", _external=True))
        r = requests.post(url=url_for("api_invoices", _external=True), headers=header, data=json.dumps(data))
        r_json = r.json()

        if "ERROR" in r_json:
            return jsonify({"status": "ERROR", "reason": r_json["ERROR"]}), 400

        events_ext_db.execute(
            """
            INSERT OR IGNORE INTO eventssold
            (uni, email, name, hash)
            VALUES (?, ?, ?, ?)
            """,
            (
                unireg,
                email,
                name,
                r_json["payment_hash"]
            ),
        )

    return jsonify({"status": "TRUE", "pay_req": r_json["pay_req"], "payment_hash": r_json["payment_hash"]}), 200


@events_ext.route("/api/v1/checkticket/", methods=["GET"])
def api_checkticket():
    """."""
    thehash = request.args.get("thehash")
    #Check databases
    with open_ext_db("events") as events_ext_db:
        eventssold = events_ext_db.fetchall("SELECT * FROM eventssold WHERE hash = ?", (thehash,))
        if not eventssold:
        	return jsonify({"status": "ERROR", "reason":"NO TICKET RECORD"}), 200
    if eventssold[0][4] == 0:
    	return jsonify({"status": "ERROR", "reason":"NOT PAID"}), 200

    with open_ext_db("events") as events_ext_db:
        events_ext_db.execute("UPDATE eventssold SET reg = 1 WHERE hash = ?", (thehash,))

    return jsonify({"status": "TRUE", "name": eventssold[0][3]}), 200
