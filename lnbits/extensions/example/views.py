#add your dependencies here

from flask import jsonify, render_template, request, redirect, url_for
from lnbits.db import open_db, open_ext_db
from lnbits.extensions.example import example_ext

#add your endpoints here

@example_ext.route("/")
def index():
    """Try to add descriptions for others."""
    usr = request.args.get("usr")

    if usr:
        if not len(usr) > 20:
            return redirect(url_for("home"))

    # Get all the data
    with open_db() as db:
        user_wallets = db.fetchall("SELECT * FROM wallets WHERE user = ?", (usr,))
        user_ext = db.fetchall("SELECT extension FROM extensions WHERE user = ? AND active = 1", (usr,))
        user_ext = [v[0] for v in user_ext]

    return render_template(
        "example/index.html"
    )
