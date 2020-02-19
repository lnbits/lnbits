#add your dependencies here
from flask import jsonify, render_template, request, redirect, url_for
from lnbits.db import open_db, open_ext_db
from lnbits.extensions.events import events_ext

#add your endpoints here

@example_ext.route("/")
def index():
    """Try to add descriptions for others."""
    return render_template(
        "example/index.html"
    )
