from flask import render_template, send_from_directory
from os import path

from lnbits.core import core_app


@core_app.route("/favicon.ico")
def favicon():
    return send_from_directory(path.join(core_app.root_path, "static"), "favicon.ico")


@core_app.route("/")
def home():
    return render_template("index.html")
