#views_api.py is for you API endpoints that could be hit by another service

#add your dependencies here

import json
import requests
from flask import jsonify, render_template, request, redirect, url_for
from lnbits.db import open_db, open_ext_db
from lnbits.extensions.tpos import tpos_ext

#add your endpoints here

@tpos_ext.route("/api/v1/fetch", methods=["GET","POST"])
def api_tpos():
    """Try to add descriptions for others."""
    
    data = request.json
    sats = data["sats"]
    pos = data["pos"]

    with open_ext_db("tpos") as events_ext_db:
        user_pos = events_ext_db.fetchall("SELECT * FROM tpos WHERE uni = ?", (pos,))
        if not user_pos:
        	return jsonify({"status": "ERROR", "reason":"NO POS"}), 400
    print(user_pos[0][4])
    header = {"Content-Type": "application/json", "Grpc-Metadata-macaroon": user_pos[0][4]}
    data = {"value": sats, "memo": "TPOS"}
    print(url_for("api_invoices", _external=True))
    r = requests.post(url=url_for("api_invoices", _external=True), headers=header, data=json.dumps(data))
    r_json = r.json()
    
    if "ERROR" in r_json:
        return jsonify({"status": "ERROR", "reason": r_json["ERROR"]}), 400

    return jsonify({"status": "TRUE","pay_req": r_json["pay_req"] ,"payment_hash": r_json["payment_hash"]  }), 200
