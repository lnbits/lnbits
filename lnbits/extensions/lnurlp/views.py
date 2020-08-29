from flask import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from lnbits.extensions.lnurlp import lnurlp_ext
from .crud import get_pay_link


@lnurlp_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def index():
    return render_template("lnurlp/index.html", user=g.user)


@lnurlp_ext.route("/<link_id>")
def display(link_id):
    link = get_pay_link(link_id) or abort(HTTPStatus.NOT_FOUND, "Pay link does not exist.")

    return render_template("lnurlp/display.html", link=link)


@lnurlp_ext.route("/print/<link_id>")
def print_qr(link_id):
    link = get_pay_link(link_id) or abort(HTTPStatus.NOT_FOUND, "Pay link does not exist.")

    return render_template("lnurlp/print_qr.html", link=link)
