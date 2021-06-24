from quart import g, abort, render_template

from lnbits.core.crud import get_wallet
from lnbits.decorators import check_user_exists, validate_uuids
from http import HTTPStatus

from . import lnticket_ext
from .crud import get_form


@lnticket_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("lnticket/index.html", user=g.user)


@lnticket_ext.route("/<form_id>")
async def display(form_id):
    form = await get_form(form_id)
    if not form:
        abort(HTTPStatus.NOT_FOUND, "LNTicket does not exist.")

    wallet = await get_wallet(form.wallet)

    return await render_template(
        "lnticket/display.html",
        form_id=form.id,
        form_name=form.name,
        form_desc=form.description,
        form_costpword=form.costpword,
        form_wallet=wallet.inkey,
    )
