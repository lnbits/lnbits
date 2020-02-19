import uuid

from flask import jsonify, render_template, request, redirect, url_for
from datetime import datetime

from lnbits.db import open_db, open_ext_db
from lnbits.extensions.events import events_ext


@events_ext.route("/")
def index():
    """Main events link page."""

    return render_template(
        "events/index.html"
    )

