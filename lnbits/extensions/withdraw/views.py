from flask import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from lnbits.extensions.withdraw import withdraw_ext
from .crud import get_withdraw_link, chunks


@withdraw_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def index():
    return render_template("withdraw/index.html", user=g.user)


@withdraw_ext.route("/<link_id>")
def display(link_id):
    link = get_withdraw_link(link_id, 0) or abort(HTTPStatus.NOT_FOUND, "Withdraw link does not exist.")
    return render_template("withdraw/display.html", link=link, unique=True)


@withdraw_ext.route("/print/<link_id>")
def print_qr(link_id):
    link = get_withdraw_link(link_id) or abort(HTTPStatus.NOT_FOUND, "Withdraw link does not exist.")
    if link.uses == 0:
        return render_template("withdraw/print_qr.html", link=link, unique=False)
    links = []
    count = 0
    for x in link.usescsv.split(","):
        linkk = get_withdraw_link(link_id, count) or abort(HTTPStatus.NOT_FOUND, "Withdraw link does not exist.")
        links.append(str(linkk.lnurl))
        count = count + 1
    page_link = list(chunks(links, 2))
    linked = list(chunks(page_link, 5))
    return render_template("withdraw/print_qr.html", link=linked, unique=True)
